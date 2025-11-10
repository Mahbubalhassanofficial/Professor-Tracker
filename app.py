import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from gspread.exceptions import WorksheetNotFound
from gspread.utils import rowcol_to_a1
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pytz

# ============================================================
# CONFIG & BRANDING
# ============================================================
st.set_page_config(
    page_title="PhD Application Planner by Mahbub Hassan",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

CHULA_PINK = "#E61E6E"
CHULA_BLUE = "#004E92"
BG = "#f8f9fa"
TEXT = "#1b1f24"
SUCCESS = "#2e7d32"
WARN = "#ed6c02"
INFO = "#0288d1"
MUTED = "#6c757d"

custom_css = f"""
<style>
/* Global */
html, body, [class*="css"]  {{
  font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, 'Helvetica Neue', Arial, 'Noto Sans', 'Liberation Sans';
  color: {TEXT};
}}
.main .block-container {{
  padding-top: 1.5rem;
  padding-bottom: 2rem;
}}
/* Header */
.app-title {{
  background: linear-gradient(90deg, {CHULA_PINK}, {CHULA_BLUE});
  color: white; padding: 18px 22px; border-radius: 16px;
  display: flex; align-items: center; gap: 16px; margin-bottom: 14px;
}}
.app-title h1 {{ margin: 0; font-size: 1.5rem; }}
.app-sub {{ opacity: 0.95; margin-top: 4px; }}
/* Cards */
.metric-card {{
  background: white; border: 1px solid #e9ecef; border-radius: 16px; padding: 16px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.04);
}}
.metric-title {{ color: {MUTED}; font-size: 0.9rem; margin-bottom: 4px; }}
.metric-value {{ font-size: 1.6rem; font-weight: 700; color: {TEXT}; }}
/* Buttons */
.stButton>button {{
  border-radius: 10px; padding: 0.5rem 1rem; font-weight: 600;
}}
/* Forms */
.stTextInput>div>div>input, .stDateInput>div>div>input, .stTextArea>div>textarea {{
  border-radius: 10px;
}}
/* Footer */
.footer {{
  margin-top: 32px; color: {MUTED}; font-size: 0.9rem; text-align: center;
}}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

with st.container():
    st.markdown(
        f"""
        <div class="app-title">
            <div>
                <h1>PhD Application Planner by Mahbub Hassan</h1>
                <div class="app-sub">Civil & Transportation Systems Research • Chulalongkorn University</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# AUTH & GOOGLE SHEETS CONNECTION
# ============================================================
# IMPORTANT: In Streamlit Cloud, set your credentials in "Settings → Secrets":
# [gcp_service_account]
# type="service_account"
# project_id="..."
# private_key_id="..."
# private_key="-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
# client_email="...@...iam.gserviceaccount.com"
# client_id="..."
# token_uri="https://oauth2.googleapis.com/token"
# universe_domain="googleapis.com"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

def make_gspread_client():
    try:
        sa_info = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(sa_info, scopes=SCOPES)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error("Google authentication failed. Please configure st.secrets['gcp_service_account'].")
        st.stop()

client = make_gspread_client()

# Let user store the Google Sheet URL (more robust than name)
with st.sidebar:
    st.header("🔗 Data Source")
    sheet_url = st.text_input(
        "Google Sheet URL",
        value=st.session_state.get("sheet_url", ""),
        placeholder="Paste the URL of 'PhD_Planner_Data' Google Sheet"
    )
    if sheet_url:
        st.session_state["sheet_url"] = sheet_url
    st.caption("Tip: Share the sheet with your service account email as **Editor**.")

def open_sheet():
    if not st.session_state.get("sheet_url"):
        st.info("Provide the Google Sheet URL in the sidebar to start.")
        st.stop()
    try:
        return client.open_by_url(st.session_state["sheet_url"])
    except Exception:
        st.error("Could not open the Google Sheet. Check URL and access permissions.")
        st.stop()

sh = open_sheet()

# ============================================================
# DATA MODEL & HELPERS
# ============================================================
TZ = pytz.timezone("Asia/Bangkok")
NOW = datetime.now(TZ)

SCHEMA = {
    "Professors": [
        "ID","Timestamp","University","Country","Professor Name","Department",
        "Research Interests","Email","Website","Contact Status","Response Date","Notes"
    ],
    "Scholarships": [
        "ID","Timestamp","Scholarship Name","Country","Deadline","Eligibility",
        "Funding Amount","Link","Status","Notes"
    ],
    "Communication": [
        "ID","Timestamp","Date","Professor","Message Type","Summary","Next Action","Follow-up Date"
    ],
    "Timeline": [
        "ID","Timestamp","Date","Task","Status","Notes"
    ]
}

STATUS_PROF = ["Not Contacted","Contacted","Replied","Ongoing","Closed"]
STATUS_SCH = ["To Explore","Applied","Shortlisted","Accepted","Rejected"]
STATUS_TASK = ["Pending","In Progress","Completed","On Hold"]

def ensure_worksheet(sheet, title, columns):
    try:
        ws = sheet.worksheet(title)
    except WorksheetNotFound:
        ws = sheet.add_worksheet(title=title, rows=1000, cols=len(columns))
        ws.insert_row(columns, 1)
    # If first row doesn't match, reset header (idempotent)
    header = ws.row_values(1)
    if header != columns:
        ws.delete_row(1)
        ws.insert_row(columns, 1)
    return ws

def read_df(title):
    ws = ensure_worksheet(sh, title, SCHEMA[title])
    data = ws.get_all_records()
    df = pd.DataFrame(data, columns=SCHEMA[title])
    return df

def new_id(df):
    if df.empty or "ID" not in df.columns:
        return 1
    return int(pd.to_numeric(df["ID"], errors="coerce").fillna(0).max()) + 1

def append_row(title, row_dict):
    ws = ensure_worksheet(sh, title, SCHEMA[title])
    values = [row_dict.get(col, "") for col in SCHEMA[title]]
    ws.append_row(values, value_input_option="USER_ENTERED")

def update_row_by_id(title, row_id, updated_dict):
    ws = ensure_worksheet(sh, title, SCHEMA[title])
    all_vals = ws.get_all_records()
    df = pd.DataFrame(all_vals, columns=SCHEMA[title])
    if df.empty:
        return False
    df["ID"] = pd.to_numeric(df["ID"], errors="coerce").astype("Int64")
    if row_id not in set(df["ID"].dropna().astype(int)):
        return False
    # Find row number (offset + 2 because 1 = header, and index starts at 0)
    idx = df.index[df["ID"] == row_id][0]
    row_number = idx + 2
    # Write each column
    for col_idx, col in enumerate(SCHEMA[title], start=1):
        value = updated_dict.get(col, "")
        ws.update_acell(rowcol_to_a1(row_number, col_idx), value)
    return True

def delete_row_by_id(title, row_id):
    ws = ensure_worksheet(sh, title, SCHEMA[title])
    all_vals = ws.get_all_records()
    df = pd.DataFrame(all_vals, columns=SCHEMA[title])
    if df.empty:
        return False
    df["ID"] = pd.to_numeric(df["ID"], errors="coerce").astype("Int64")
    if row_id not in set(df["ID"].dropna().astype(int)):
        return False
    idx = df.index[df["ID"] == row_id][0]
    ws.delete_rows(idx + 2, idx + 2)
    return True

def parse_date(x):
    if pd.isna(x) or x == "":
        return None
    try:
        return pd.to_datetime(x)
    except Exception:
        try:
            return pd.to_datetime(x, format="%Y-%m-%d")
        except Exception:
            return None

# ============================================================
# DASHBOARD
# ============================================================
def render_dashboard():
    prof = read_df("Professors")
    sch = read_df("Scholarships")
    com = read_df("Communication")

    with st.container():
        c1, c2, c3, c4, c5 = st.columns(5)
        total_prof = len(prof)
        contacted = int((prof["Contact Status"] == "Contacted").sum()) if not prof.empty else 0
        replied = int((prof["Contact Status"] == "Replied").sum()) if not prof.empty else 0
        total_sch = len(sch)
        # deadlines within next 30 days
        close_soon = 0
        if not sch.empty:
            dd = pd.to_datetime(sch["Deadline"], errors="coerce")
            close_soon = int(((dd - pd.Timestamp(NOW.date())) <= pd.Timedelta(days=30)).sum())

        for col, title, value in [
            (c1, "Total Professors", total_prof),
            (c2, "Contacted", contacted),
            (c3, "Replies", replied),
            (c4, "Scholarships", total_sch),
            (c5, "Deadlines ≤ 30d", close_soon),
        ]:
            with col:
                st.markdown(f"""
                <div class="metric-card">
                  <div class="metric-title">{title}</div>
                  <div class="metric-value">{value}</div>
                </div>
                """, unsafe_allow_html=True)

    st.divider()

    # Charts
    st.subheader("Visual Overview")

    cols = st.columns(2)
    with cols[0]:
        if not prof.empty:
            fig = px.histogram(prof, x="Country", color="Contact Status", barmode="group", title="Professors by Country & Status")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Professor data will appear here.")

    with cols[1]:
        if not sch.empty:
            tmp = sch.copy()
            tmp["Deadline"] = pd.to_datetime(tmp["Deadline"], errors="coerce")
            tmp = tmp.dropna(subset=["Deadline"]).sort_values("Deadline").head(20)
            fig = px.bar(tmp, x="Deadline", y="Scholarship Name", orientation="h", title="Upcoming Scholarship Deadlines")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Scholarship data will appear here.")

# ============================================================
# PROFESSOR TRACKER
# ============================================================
def render_professors():
    st.subheader("Professor Tracker")

    df = read_df("Professors")

    with st.expander("Add New Professor", expanded=True):
        with st.form("add_prof"):
            c1, c2, c3 = st.columns(3)
            university = c1.text_input("University")
            country = c2.text_input("Country")
            dept = c3.text_input("Department")
            c4, c5, c6 = st.columns(3)
            name = c4.text_input("Professor Name")
            interests = c5.text_input("Research Interests (e.g., CAV, SUMO, ITS)")
            email = c6.text_input("Email")
            c7, c8, c9 = st.columns(3)
            website = c7.text_input("Website / Profile URL")
            status = c8.selectbox("Contact Status", STATUS_PROF, index=0)
            response_date = c9.date_input("Response Date (optional)", value=None)
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Add Professor", use_container_width=True)
        if submitted:
            row = {
                "ID": new_id(df),
                "Timestamp": NOW.strftime("%Y-%m-%d %H:%M:%S"),
                "University": university.strip(),
                "Country": country.strip(),
                "Professor Name": name.strip(),
                "Department": dept.strip(),
                "Research Interests": interests.strip(),
                "Email": email.strip(),
                "Website": website.strip(),
                "Contact Status": status,
                "Response Date": response_date.strftime("%Y-%m-%d") if response_date else "",
                "Notes": notes.strip(),
            }
            append_row("Professors", row)
            st.success("Professor added.")

    st.markdown("### Browse / Edit")
    if df.empty:
        st.info("No data yet.")
        return
    # Filters
    fc1, fc2, fc3 = st.columns(3)
    f_country = fc1.text_input("Filter by Country")
    f_status = fc2.selectbox("Filter by Status", ["All"] + STATUS_PROF, index=0)
    f_text = fc3.text_input("Search (name, interests, university)")

    dff = df.copy()
    if f_country:
        dff = dff[dff["Country"].str.contains(f_country, case=False, na=False)]
    if f_status != "All":
        dff = dff[dff["Contact Status"] == f_status]
    if f_text:
        mask = (
            dff["Professor Name"].str.contains(f_text, case=False, na=False) |
            dff["University"].str.contains(f_text, case=False, na=False) |
            dff["Research Interests"].str.contains(f_text, case=False, na=False)
        )
        dff = dff[mask]

    st.dataframe(dff, use_container_width=True, hide_index=True)

    st.markdown("### Update or Delete")
    ids = dff["ID"].tolist() if not dff.empty else []
    if ids:
        col_a, col_b = st.columns([2,1])
        with col_a:
            sel_id = st.selectbox("Select ID to edit/delete", ids)
        selected = df[df["ID"] == sel_id].iloc[0]

        with st.form("edit_prof"):
            e1, e2, e3 = st.columns(3)
            university = e1.text_input("University", selected["University"])
            country = e2.text_input("Country", selected["Country"])
            dept = e3.text_input("Department", selected["Department"])
            e4, e5, e6 = st.columns(3)
            name = e4.text_input("Professor Name", selected["Professor Name"])
            interests = e5.text_input("Research Interests", selected["Research Interests"])
            email = e6.text_input("Email", selected["Email"])
            e7, e8, e9 = st.columns(3)
            website = e7.text_input("Website / Profile URL", selected["Website"])
            status = e8.selectbox("Contact Status", STATUS_PROF, index=STATUS_PROF.index(selected["Contact Status"]) if selected["Contact Status"] in STATUS_PROF else 0)
            resp_parsed = parse_date(selected["Response Date"])
            resp_date = e9.date_input("Response Date (optional)", value=resp_parsed.date() if resp_parsed else None)
            notes = st.text_area("Notes", selected["Notes"])
            c_upd, c_del = st.columns(2)
            upd = c_upd.form_submit_button("Save Changes", use_container_width=True)
            delete = c_del.form_submit_button("Delete", use_container_width=True)

        if upd:
            row = {
                "ID": int(sel_id),
                "Timestamp": selected["Timestamp"],
                "University": university.strip(),
                "Country": country.strip(),
                "Professor Name": name.strip(),
                "Department": dept.strip(),
                "Research Interests": interests.strip(),
                "Email": email.strip(),
                "Website": website.strip(),
                "Contact Status": status,
                "Response Date": resp_date.strftime("%Y-%m-%d") if resp_date else "",
                "Notes": notes.strip(),
            }
            ok = update_row_by_id("Professors", int(sel_id), row)
            if ok: st.success("Updated.")
            else: st.error("Update failed.")
        if delete:
            ok = delete_row_by_id("Professors", int(sel_id))
            if ok: st.success("Deleted.")
            else: st.error("Delete failed.")

# ============================================================
# SCHOLARSHIPS
# ============================================================
def render_scholarships():
    st.subheader("Scholarship & Funding Tracker")

    df = read_df("Scholarships")

    with st.expander("Add Scholarship", expanded=True):
        with st.form("add_sch"):
            c1, c2, c3 = st.columns(3)
            name = c1.text_input("Scholarship Name")
            country = c2.text_input("Country / Region")
            deadline = c3.date_input("Deadline")
            c4, c5, c6 = st.columns(3)
            eligibility = c4.text_area("Eligibility (short)")
            funding = c5.text_input("Funding Amount / Duration")
            link = c6.text_input("Official Link")
            c7, c8 = st.columns(2)
            status = c7.selectbox("Status", STATUS_SCH, index=0)
            notes = c8.text_area("Notes")
            submitted = st.form_submit_button("Add Scholarship", use_container_width=True)
        if submitted:
            row = {
                "ID": new_id(df),
                "Timestamp": NOW.strftime("%Y-%m-%d %H:%M:%S"),
                "Scholarship Name": name.strip(),
                "Country": country.strip(),
                "Deadline": deadline.strftime("%Y-%m-%d"),
                "Eligibility": eligibility.strip(),
                "Funding Amount": funding.strip(),
                "Link": link.strip(),
                "Status": status,
                "Notes": notes.strip(),
            }
            append_row("Scholarships", row)
            st.success("Scholarship added.")

    st.markdown("### Browse / Filters")
    if df.empty:
        st.info("No data yet.")
        return

    fc1, fc2, fc3 = st.columns(3)
    f_country = fc1.text_input("Filter by Country")
    f_status = fc2.selectbox("Filter by Status", ["All"] + STATUS_SCH, index=0)
    only_soon = fc3.checkbox("Show deadlines within 30 days", value=False)

    dff = df.copy()
    if f_country:
        dff = dff[dff["Country"].str.contains(f_country, case=False, na=False)]
    if f_status != "All":
        dff = dff[dff["Status"] == f_status]
    if only_soon:
        dff["Deadline_dt"] = pd.to_datetime(dff["Deadline"], errors="coerce")
        dff = dff[(dff["Deadline_dt"] - pd.Timestamp(NOW.date())) <= pd.Timedelta(days=30)]

    st.dataframe(dff.drop(columns=[c for c in ["Deadline_dt"] if c in dff.columns]), use_container_width=True, hide_index=True)

    st.markdown("### Update or Delete")
    ids = dff["ID"].tolist()
    if ids:
        sel_id = st.selectbox("Select ID to edit/delete", ids)
        selected = df[df["ID"] == sel_id].iloc[0]
        with st.form("edit_sch"):
            e1, e2, e3 = st.columns(3)
            name = e1.text_input("Scholarship Name", selected["Scholarship Name"])
            country = e2.text_input("Country / Region", selected["Country"])
            deadline = parse_date(selected["Deadline"])
            deadline = e3.date_input("Deadline", value=deadline.date() if deadline else NOW.date())
            e4, e5, e6 = st.columns(3)
            eligibility = e4.text_area("Eligibility (short)", selected["Eligibility"])
            funding = e5.text_input("Funding Amount / Duration", selected["Funding Amount"])
            link = e6.text_input("Official Link", selected["Link"])
            e7, e8 = st.columns(2)
            status = e7.selectbox("Status", STATUS_SCH, index=STATUS_SCH.index(selected["Status"]) if selected["Status"] in STATUS_SCH else 0)
            notes = e8.text_area("Notes", selected["Notes"])
            c_upd, c_del = st.columns(2)
            upd = c_upd.form_submit_button("Save Changes", use_container_width=True)
            delete = c_del.form_submit_button("Delete", use_container_width=True)
        if upd:
            row = {
                "ID": int(sel_id),
                "Timestamp": selected["Timestamp"],
                "Scholarship Name": name.strip(),
                "Country": country.strip(),
                "Deadline": deadline.strftime("%Y-%m-%d"),
                "Eligibility": eligibility.strip(),
                "Funding Amount": funding.strip(),
                "Link": link.strip(),
                "Status": status,
                "Notes": notes.strip(),
            }
            ok = update_row_by_id("Scholarships", int(sel_id), row)
            if ok: st.success("Updated.")
            else: st.error("Update failed.")
        if delete:
            ok = delete_row_by_id("Scholarships", int(sel_id))
            if ok: st.success("Deleted.")
            else: st.error("Delete failed.")

# ============================================================
# COMMUNICATION LOG (Auto-updates Professor Status to "Replied")
# ============================================================
def render_communication():
    st.subheader("Communication Log")

    prof_df = read_df("Professors")
    df = read_df("Communication")

    with st.expander("Add Communication", expanded=True):
        with st.form("add_com"):
            c1, c2, c3 = st.columns(3)
            date = c1.date_input("Date", value=NOW.date())
            professor = c2.selectbox("Professor", [""] + prof_df["Professor Name"].dropna().astype(str).tolist())
            msg_type = c3.selectbox("Message Type", ["Email (Outgoing)", "Email (Incoming)", "Call", "Meeting", "Other"])
            summary = st.text_area("Summary / Key Points")
            n1, n2 = st.columns(2)
            next_action = n1.text_input("Next Action (e.g., Send CV, Schedule call)")
            followup_date = n2.date_input("Follow-up Date (optional)", value=None)
            submitted = st.form_submit_button("Add Log", use_container_width=True)

        if submitted:
            row_dict = {
                "ID": new_id(df),
                "Timestamp": NOW.strftime("%Y-%m-%d %H:%M:%S"),
                "Date": date.strftime("%Y-%m-%d"),
                "Professor": professor.strip(),
                "Message Type": msg_type,
                "Summary": summary.strip(),
                "Next Action": next_action.strip(),
                "Follow-up Date": followup_date.strftime("%Y-%m-%d") if followup_date else "",
            }
            append_row("Communication", row_dict)
            st.success("Communication logged.")

            # Auto-update Professor status if incoming email (reply)
            if "Incoming" in msg_type and professor:
                # Find the professor and set status + response date
                p = prof_df[prof_df["Professor Name"] == professor]
                if not p.empty:
                    pid = int(p.iloc[0]["ID"])
                    updated = p.iloc[0].to_dict()
                    updated["Contact Status"] = "Replied"
                    updated["Response Date"] = date.strftime("%Y-%m-%d")
                    ok = update_row_by_id("Professors", pid, updated)
                    if ok:
                        st.success(f"Auto-updated {professor} status to 'Replied'.")

    st.markdown("### Browse / Filter")
    df = read_df("Communication")
    if df.empty:
        st.info("No communication yet.")
        return

    fc1, fc2 = st.columns(2)
    f_prof = fc1.text_input("Filter by Professor")
    f_type = fc2.selectbox("Type", ["All","Email (Outgoing)","Email (Incoming)","Call","Meeting","Other"], index=0)

    dff = df.copy()
    if f_prof:
        dff = dff[dff["Professor"].str.contains(f_prof, case=False, na=False)]
    if f_type != "All":
        dff = dff[dff["Message Type"] == f_type]
    st.dataframe(dff, use_container_width=True, hide_index=True)

# ============================================================
# TIMELINE
# ============================================================
def render_timeline():
    st.subheader("Application Timeline & Tasks")

    df = read_df("Timeline")

    with st.expander("Add Task", expanded=True):
        with st.form("add_task"):
            c1, c2, c3 = st.columns(3)
            date = c1.date_input("Date", value=NOW.date())
            task = c2.text_input("Task")
            status = c3.selectbox("Status", STATUS_TASK, index=0)
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Add Task", use_container_width=True)
        if submitted:
            row = {
                "ID": new_id(df),
                "Timestamp": NOW.strftime("%Y-%m-%d %H:%M:%S"),
                "Date": date.strftime("%Y-%m-%d"),
                "Task": task.strip(),
                "Status": status,
                "Notes": notes.strip(),
            }
            append_row("Timeline", row)
            st.success("Task added.")

    st.markdown("### Tasks")
    if df.empty:
        st.info("No tasks yet.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Simple timeline chart (bar by date)
    try:
        tmp = df.copy()
        tmp["Date"] = pd.to_datetime(tmp["Date"], errors="coerce")
        tmp = tmp.dropna(subset=["Date"]).sort_values("Date")
        tmp["End"] = tmp["Date"] + pd.to_timedelta(1, unit="D")
        fig = px.timeline(tmp, x_start="Date", x_end="End", y="Task", color="Status", title="Timeline (1-day blocks)")
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        st.info("Add more valid dates to render the timeline chart.")

# ============================================================
# NAVIGATION
# ============================================================
tabs = st.tabs(["🏠 Dashboard","👨‍🏫 Professors","💰 Scholarships","✉️ Communication","🗓️ Timeline"])

with tabs[0]:
    render_dashboard()
with tabs[1]:
    render_professors()
with tabs[2]:
    render_scholarships()
with tabs[3]:
    render_communication()
with tabs[4]:
    render_timeline()

st.markdown(
    f"""
    <div class="footer">
      © 2025 Mahbub Hassan • Academic Research Tools • Chulalongkorn University
    </div>
    """,
    unsafe_allow_html=True
)
