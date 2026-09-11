import streamlit as st
from supabase import create_client
from datetime import datetime, date
from io import BytesIO
from zoneinfo import ZoneInfo
import pandas as pd


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="College Attendance System",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ============================================================
# MODERN UI STYLING
# ============================================================

st.markdown("""
<style>
    /* Global Container Adjustments */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    
    /* Custom Badges */
    .status-badge {
        display: inline-block;
        padding: 4px 10px;
        font-size: 0.82rem;
        font-weight: 600;
        border-radius: 20px;
        text-align: center;
    }
    .badge-present { background-color: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; }
    .badge-absent { background-color: #fee2e2; color: #b91c1c; border: 1px solid #fecaca; }
    .badge-pending { background-color: #fef3c7; color: #b45309; border: 1px solid #fde68a; }
    .badge-inactive { background-color: #f1f5f9; color: #64748b; border: 1px solid #e2e8f0; }
    
    /* Header Bar */
    .top-header {
        background: linear-gradient(90deg, #1e293b 0%, #0f172a 100%);
        color: #ffffff;
        padding: 20px 24px;
        border-radius: 14px;
        margin-bottom: 24px;
        box-shadow: 0 10px 15px -3px rgba(15, 23, 42, 0.15);
    }
    .top-header h1 {
        color: #ffffff !important;
        margin: 0;
        font-size: 1.8rem;
        font-weight: 700;
    }
    .top-header p {
        color: #94a3b8 !important;
        margin: 4px 0 0 0;
        font-size: 0.95rem;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# SUPABASE CONNECTION
# ============================================================

@st.cache_resource
def get_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

try:
    supabase = get_supabase()
except Exception as e:
    st.error("⚠️ Failed to connect to Supabase. Please verify your secrets configuration.")
    st.stop()


# ============================================================
# TIMEZONE SETUP
# ============================================================

india_time = datetime.now(ZoneInfo("Asia/Kolkata"))


# ============================================================
# SESSION STATE INITIALIZATION
# ============================================================

if "faculty_name" not in st.session_state:
    st.session_state.faculty_name = ""

if "show_attendance_table" not in st.session_state:
    st.session_state.show_attendance_table = False


# ============================================================
# DATABASE HELPER FUNCTIONS
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_all_students():
    all_students = []
    start = 0
    page_size = 1000

    while True:
        response = (
            supabase
            .table("students")
            .select("student_id, student_name, branch, batch, active")
            .range(start, start + page_size - 1)
            .execute()
        )
        batch = response.data or []
        all_students.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size

    return all_students


def save_bulk_attendance(records_list):
    """Saves multiple attendance records in a single batch database call."""
    if not records_list:
        return None
    return (
        supabase
        .table("attendance")
        .upsert(records_list, on_conflict="student_id,attendance_date")
        .execute()
    )


# ============================================================
# TOP HEADER BAR
# ============================================================

st.markdown(
    f"""
    <div class="top-header">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
            <div>
                <h1>📋 College Attendance Portal</h1>
                <p>Date: <strong>{india_time.strftime('%A, %d %B %Y')}</strong></p>
            </div>
            <div style="text-align: right;">
                <span style="background: rgba(255,255,255,0.15); padding: 6px 14px; border-radius: 20px; font-size: 0.9rem;">
                    ⚡ Fast Sync Mode
                </span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# FACULTY AUTHENTICATION GATE
# ============================================================

if not st.session_state.faculty_name:
    st.subheader("👨‍🏫 Faculty Portal Sign-in")
    
    col_a, col_b = st.columns([2, 1])
    with col_a:
        faculty_input = st.text_input(
            "Enter Faculty / Staff Name",
            placeholder="e.g. Dr. S. Kumar",
            key="faculty_login_input"
        )
        if st.button("Continue to Dashboard", type="primary", use_container_width=True):
            if faculty_input.strip():
                st.session_state.faculty_name = faculty_input.strip()
                st.rerun()
            else:
                st.warning("Please enter your name to proceed.")
    st.stop()


f_col1, f_col2 = st.columns([5, 1])
with f_col1:
    st.info(f"👨‍🏫 Logged in as: **{st.session_state.faculty_name}**")
with f_col2:
    if st.button("Logout / Change", use_container_width=True):
        st.session_state.faculty_name = ""
        st.session_state.show_attendance_table = False
        st.rerun()

faculty_name = st.session_state.faculty_name


# ============================================================
# SELECTION FORM (Date, Course, Branch, Show Button)
# ============================================================

st.subheader("📝 Attendance Selection")

att_type = st.radio("Attendance Type", ["Regular", "Substitute"], horizontal=True)

col_sel1, col_sel2 = st.columns([1, 2])

with col_sel1:
    selected_date = st.date_input("Date :", value=india_time.date())
    selected_course = st.selectbox("Course:", ["B.Tech", "M.Tech", "MBA", "MCA"])
    
    all_students = get_all_students()
    branch_options = sorted(
        {str(s.get("branch", "")).strip() for s in all_students if str(s.get("branch", "")).strip()}
    )
    if not branch_options:
        branch_options = ["COMPUTER SCIENCE ENGINEERING", "ELECTRONICS & COMM", "MECHANICAL", "CIVIL"]
        
    selected_branch = st.selectbox("Branch:", branch_options)

    if st.button("Show", type="primary"):
        st.session_state.show_attendance_table = True

st.divider()


# ============================================================
# ATTENDANCE TABLE & ONE-CLICK ABSENTEES / PRESENTEES
# ============================================================

if st.session_state.show_attendance_table:
    
    check_mode = st.radio(
        "Bulk Selection Mode:",
        ["Check Absentees", "Check Presentees"],
        horizontal=True,
        index=0
    )

    filtered_students = [
        s for s in all_students
        if str(s.get("branch", "")).strip() == selected_branch
    ]
    filtered_students = sorted(filtered_students, key=lambda x: str(x.get("student_name", "")).lower())

    if not filtered_students:
        st.warning("No students found for the selected branch.")
    else:
        st.write("")
        
        # Exact Requested Headers
        h1, h2, h3, h4 = st.columns([1.5, 3.5, 2, 2])
        with h1: st.markdown("**Student ID**")
        with h2: st.markdown("**Student Name / Batch**")
        with h3: st.markdown("**Today's Status**")
        with h4: st.markdown("**Mark Present / Absent**")
        
        st.divider()

        formatted_date_str = selected_date.strftime("%Y-%m-%d")
        bulk_records = []

        # Render Student Rows
        for student in filtered_students:
            s_id = str(student["student_id"])
            s_name = student["student_name"]
            s_batch = student.get("batch", "N/A")

            r1, r2, r3, r4 = st.columns([1.5, 3.5, 2, 2])

            with r1:
                st.write(f"`{s_id}`")

            with r2:
                st.markdown(f"**{s_name}**  \n<span style='color: #64748b; font-size: 0.82rem;'>Batch {s_batch}</span>", unsafe_allow_html=True)

            with r4:
                default_checked = True if check_mode == "Check Absentees" else False
                
                is_checked = st.checkbox(
                    "", 
                    value=default_checked, 
                    key=f"chk_{selected_branch}_{s_id}_{check_mode}"
                )
                
                if check_mode == "Check Absentees":
                    status_value = "Absent" if is_checked else "Present"
                else:
                    status_value = "Present" if is_checked else "Absent"

            with r3:
                if status_value == "Present":
                    st.markdown("<span class='status-badge badge-present'>Present</span>", unsafe_allow_html=True)
                else:
                    st.markdown("<span class='status-badge badge-absent'>Absent</span>", unsafe_allow_html=True)

            bulk_records.append({
                "student_id": int(s_id) if s_id.isdigit() else s_id,
                "attendance_date": formatted_date_str,
                "status": status_value,
                "marked_by": faculty_name,
                "marked_at": india_time.isoformat()
            })

        st.divider()

        # Submit / Post Button
        if st.button(
            f"⚡ Post / Save Attendance to Database ({len(bulk_records)} Students)",
            type="primary",
            use_container_width=True
        ):
            with st.spinner("Posting attendance to database..."):
                try:
                    save_bulk_attendance(bulk_records)
                    st.success(f"✅ Successfully posted attendance for {len(bulk_records)} students on {formatted_date_str}!")
                except Exception as e:
                    st.error(f"Failed to post attendance: {e}")
