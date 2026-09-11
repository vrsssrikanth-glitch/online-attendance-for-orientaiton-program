import streamlit as st
from supabase import create_client
from datetime import datetime
from zoneinfo import ZoneInfo

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="College Attendance System",
    page_icon="📋",
    layout="wide"
)

# Custom Styling
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    .status-badge {
        display: inline-block;
        padding: 4px 10px;
        font-size: 0.85rem;
        font-weight: 600;
        border-radius: 12px;
        text-align: center;
    }
    .badge-present { background-color: #dcfce7; color: #15803d; }
    .badge-absent { background-color: #fee2e2; color: #b91c1c; }
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
    st.error("⚠️ Failed to connect to Supabase. Check your secrets configuration.")
    st.stop()

india_time = datetime.now(ZoneInfo("Asia/Kolkata"))

# Session state initialization
if "show_table" not in st.session_state:
    st.session_state.show_table = False

# ============================================================
# DATABASE HELPERS
# ============================================================

def get_filtered_students(course, branch):
    """Fetches students based on top filter selections."""
    try:
        query = supabase.table("students").select("student_id, student_name, batch, active")
        
        if branch:
            query = query.eq("branch", branch)
            
        res = query.execute()
        return res.data or []
    except Exception as e:
        st.error(f"Error fetching students: {e}")
        return []

def save_bulk_attendance(records_list):
    """Saves/upserts attendance records into database."""
    if not records_list:
        return None
    return (
        supabase
        .table("attendance")
        .upsert(records_list, on_conflict="student_id,attendance_date")
        .execute()
    )

# ============================================================
# FILTER UI
# ============================================================

st.write("### Attendance Entry Portal")

col_type, col_empty = st.columns([2, 3])
with col_type:
    att_type = st.radio("Attendance Type", ["Regular", "Substitute"], horizontal=True)

col_f1, col_f2 = st.columns([1, 2])

with col_f1:
    selected_date = st.date_input("Date :", value=india_time.date())
    selected_course = st.selectbox("Course:", ["B.Tech", "M.Tech", "MBA", "MCA"])
    selected_branch = st.selectbox("Branch:", ["COMPUTER SCIENCE ENGINEERING", "ELECTRONICS & COMM", "MECHANICAL", "CIVIL"])

    if st.button("Show", type="primary"):
        st.session_state.show_table = True

st.divider()

# ============================================================
# ATTENDANCE LIST & ONE-CLICK SELECTION
# ============================================================

if st.session_state.show_table:
    
    # 1-Click Action Selection
    check_mode = st.radio(
        "Bulk Selection Mode:",
        ["Check Absentees", "Check Presentees"],
        horizontal=True,
        index=0
    )

    students = get_filtered_students(selected_course, selected_branch)

    if not students:
        st.warning("No students found for the selected filter criteria.")
    else:
        st.write("")
        
        # Updated Table Header Row
        h1, h2, h3, h4 = st.columns([2, 4, 2, 2])
        with h1: st.markdown("**Student ID**")
        with h2: st.markdown("**Student Name / Batch**")
        with h3: st.markdown("**Today's Status**")
        with h4: st.markdown("**Mark Present / Absent**")
        st.divider()

        formatted_db_date = selected_date.strftime("%Y-%m-%d")
        attendance_submission = []

        # Render Student Rows
        for student in students:
            s_id = str(student["student_id"])
            s_name = student["student_name"]
            s_batch = student.get("batch", "N/A")

            r1, r2, r3, r4 = st.columns([2, 4, 2, 2])

            # Column 1: Student ID
            with r1:
                st.write(f"`{s_id}`")
                
            # Column 2: Student Name / Batch
            with r2:
                st.markdown(f"**{s_name}**  \n<span style='color: #64748b; font-size: 0.82rem;'>Batch {s_batch}</span>", unsafe_allow_html=True)
                
            # Column 4: Mark Present / Absent (Checkbox)
            with r4:
                default_checked = True if check_mode == "Check Absentees" else False
                
                is_checked = st.checkbox(
                    "", 
                    value=default_checked, 
                    key=f"chk_{s_id}_{check_mode}"
                )
                
                if check_mode == "Check Absentees":
                    status = "Absent" if is_checked else "Present"
                else:
                    status = "Present" if is_checked else "Absent"

            # Column 3: Today's Status Badge (Reflects live selection)
            with r3:
                if status == "Present":
                    st.markdown("<span class='status-badge badge-present'>Present</span>", unsafe_allow_html=True)
                else:
                    st.markdown("<span class='status-badge badge-absent'>Absent</span>", unsafe_allow_html=True)

            attendance_submission.append({
                "student_id": s_id,
                "attendance_date": formatted_db_date,
                "status": status,
                "marked_by": "Faculty",
                "marked_at": india_time.isoformat()
            })

        st.divider()

        # Submit Button to Save to Database
        if st.button("💾 Post / Save Attendance to Database", type="primary", use_container_width=True):
            with st.spinner("Posting attendance to database..."):
                try:
                    save_bulk_attendance(attendance_submission)
                    st.success(f"✅ Successfully posted attendance for {len(attendance_submission)} students on {formatted_db_date}!")
                except Exception as e:
                    st.error(f"Failed to post attendance: {e}")
