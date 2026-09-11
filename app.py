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
    
    /* Modern Card Styles */
    .metric-card {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 18px 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        text-align: center;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08);
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

    /* Expander Polish */
    div[data-testid="stExpander"] {
        border-radius: 10px;
        border: 1px solid #e2e8f0;
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
# TIMEZONE & DATE SETUP
# ============================================================

india_time = datetime.now(ZoneInfo("Asia/Kolkata"))
today = india_time.date().isoformat()
current_time = india_time.isoformat()


# ============================================================
# SESSION STATE INITIALIZATION
# ============================================================

if "faculty_name" not in st.session_state:
    st.session_state.faculty_name = ""

if "report_df" not in st.session_state:
    st.session_state.report_df = None

if "selected_students" not in st.session_state:
    st.session_state.selected_students = set()


# ============================================================
# DATABASE HELPER FUNCTIONS
# ============================================================

def get_total_strength():
    response = (
        supabase
        .table("students")
        .select("student_id", count="exact")
        .eq("active", True)
        .execute()
    )
    return response.count or 0


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


def get_today_attendance():
    all_records = []
    start = 0
    page_size = 1000

    while True:
        response = (
            supabase
            .table("attendance")
            .select("student_id, attendance_date, status, marked_by, marked_at")
            .eq("attendance_date", today)
            .range(start, start + page_size - 1)
            .execute()
        )
        batch = response.data or []
        all_records.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size

    return all_records


def search_students(search_text):
    search_text = search_text.strip()
    if not search_text:
        return []

    response = (
        supabase
        .table("students")
        .select("student_id, student_name, branch, batch, active")
        .ilike("student_name", f"%{search_text}%")
        .limit(20)
        .execute()
    )
    students = response.data or []

    if not students:
        try:
            numeric_id = int(search_text)
            response = (
                supabase
                .table("students")
                .select("student_id, student_name, branch, batch, active")
                .eq("student_id", numeric_id)
                .limit(20)
                .execute()
            )
            students = response.data or []
        except ValueError:
            response = (
                supabase
                .table("students")
                .select("student_id, student_name, branch, batch, active")
                .ilike("student_id", f"%{search_text}%")
                .limit(20)
                .execute()
            )
            students = response.data or []

    return students


def get_student_attendance(student_id):
    response = (
        supabase
        .table("attendance")
        .select("student_id, attendance_date, status, marked_by, marked_at")
        .eq("student_id", student_id)
        .eq("attendance_date", today)
        .limit(1)
        .execute()
    )
    records = response.data or []
    return records[0] if records else None


def save_attendance(student_id, status, faculty_name):
    data = {
        "student_id": student_id,
        "attendance_date": today,
        "status": status,
        "marked_by": faculty_name,
        "marked_at": current_time
    }
    return (
        supabase
        .table("attendance")
        .upsert(data, on_conflict="student_id,attendance_date")
        .execute()
    )


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


def update_attendance(student_id, status, faculty_name):
    return (
        supabase
        .table("attendance")
        .update({
            "status": status,
            "marked_by": faculty_name,
            "marked_at": current_time
        })
        .eq("student_id", student_id)
        .eq("attendance_date", today)
        .execute()
    )


def get_all_attendance():
    all_records = []
    start = 0
    page_size = 1000

    while True:
        response = (
            supabase
            .table("attendance")
            .select("student_id, attendance_date, status, marked_by, marked_at")
            .order("attendance_date")
            .order("student_id")
            .range(start, start + page_size - 1)
            .execute()
        )
        batch = response.data or []
        all_records.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size

    return all_records


def get_complete_attendance_report():
    students = get_all_students()
    attendance = get_all_attendance()

    if not students:
        return pd.DataFrame()

    students_df = pd.DataFrame(students)

    if not attendance:
        return students_df[["student_id", "student_name", "branch", "batch"]].rename(
            columns={
                "student_id": "Student ID",
                "student_name": "Student Name",
                "branch": "Branch",
                "batch": "Batch"
            }
        )

    attendance_df = pd.DataFrame(attendance)
    attendance_df["attendance_date"] = pd.to_datetime(
        attendance_df["attendance_date"], errors="coerce"
    ).dt.date
    attendance_df = attendance_df.dropna(subset=["attendance_date"])

    if attendance_df.empty:
        return students_df[["student_id", "student_name", "branch", "batch"]].rename(
            columns={
                "student_id": "Student ID",
                "student_name": "Student Name",
                "branch": "Branch",
                "batch": "Batch"
            }
        )

    first_date = min(attendance_df["attendance_date"])
    last_date = india_time.date()

    all_dates = pd.date_range(start=first_date, end=last_date, freq="D").date

    attendance_df = attendance_df.drop_duplicates(
        subset=["student_id", "attendance_date"], keep="last"
    )

    attendance_pivot = (
        attendance_df
        .pivot(index="student_id", columns="attendance_date", values="status")
        .reindex(columns=all_dates)
        .reset_index()
    )

    report = students_df.merge(attendance_pivot, on="student_id", how="left")
    date_columns = [col for col in report.columns if isinstance(col, date)]

    for col in date_columns:
        report[col] = report[col].fillna("Not Marked").replace("", "Not Marked")

    report = report.sort_values(by=["branch", "student_name"], kind="stable")

    rename_columns = {
        "student_id": "Student ID",
        "student_name": "Student Name",
        "branch": "Branch",
        "batch": "Batch"
    }

    for col in date_columns:
        rename_columns[col] = col.strftime("%d-%m-%Y")

    report = report.rename(columns=rename_columns)

    fixed_columns = ["Student ID", "Student Name", "Branch", "Batch"]
    date_column_names = [d.strftime("%d-%m-%Y") for d in all_dates]

    report = report[fixed_columns + date_column_names]
    return report


def create_branch_wise_excel(report_df):
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        date_columns = [
            col for col in report_df.columns
            if col not in ["Student ID", "Student Name", "Branch", "Batch"]
        ]

        summary_rows = []
        for branch, branch_df in report_df.groupby("Branch", sort=True):
            total_students = len(branch_df)
            total_present = sum(
                (
                    branch_df[date_columns]
                    .astype(str)
                    .apply(lambda col: col.str.strip().str.lower() == "present")
                    .sum()
                )
            )
            total_possible = total_students * len(date_columns)
            percentage = (total_present / total_possible * 100) if total_possible > 0 else 0

            summary_rows.append({
                "Branch": branch,
                "Total Students": total_students,
                "Total Present": int(total_present),
                "Total Attendance Entries": total_possible,
                "Attendance %": round(percentage, 2)
            })

        summary_df = pd.DataFrame(summary_rows)
        if not summary_df.empty:
            summary_df.to_excel(writer, index=False, sheet_name="Summary")

        for branch, branch_df in report_df.groupby("Branch", sort=True):
            safe_sheet_name = str(branch)
            for char in ["\\", "/", "*", "[", "]", ":", "?"]:
                safe_sheet_name = safe_sheet_name.replace(char, "_")
            safe_sheet_name = (safe_sheet_name[:31] or "Branch")

            branch_df.to_excel(writer, index=False, sheet_name=safe_sheet_name)

        workbook = writer.book
        for worksheet in workbook.worksheets:
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions

            for cell in worksheet[1]:
                cell.font = cell.font.copy(bold=True)

            for column_cells in worksheet.columns:
                column_letter = column_cells[0].column_letter
                max_length = 0
                for cell in column_cells:
                    value = "" if cell.value is None else str(cell.value)
                    max_length = max(max_length, len(value))
                worksheet.column_dimensions[column_letter].width = min(
                    max(max_length + 2, 12), 30
                )

    return output.getvalue()


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
                    ⚡ High-Speed Sync
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
        st.session_state.report_df = None
        st.session_state.selected_students = set()
        st.rerun()

faculty_name = st.session_state.faculty_name


# ============================================================
# FETCH LIVE METRICS
# ============================================================

try:
    total_strength = get_total_strength()
except Exception as e:
    st.error(f"Error fetching total strength: {e}")
    total_strength = 0

try:
    today_records = get_today_attendance()
except Exception as e:
    st.error(f"Error fetching today's records: {e}")
    today_records = []

present_count = sum(
    1 for r in today_records if str(r.get("status", "")).strip().lower() == "present"
)
absent_count = sum(
    1 for r in today_records if str(r.get("status", "")).strip().lower() == "absent"
)
not_marked_count = max(0, total_strength - present_count - absent_count)
percentage = (present_count / total_strength * 100) if total_strength > 0 else 0.0


# ============================================================
# NAVIGATION TABS
# ============================================================

tab_dash, tab_branch, tab_search, tab_reports = st.tabs([
    "📊 Today's Dashboard",
    "📝 Mark Attendance (Branch View)",
    "🔍 Quick Student Search",
    "📈 Export Reports"
])


# ------------------------------------------------------------
# TAB 1: DASHBOARD
# ------------------------------------------------------------
with tab_dash:
    d_col1, d_col2 = st.columns([3, 1])
    with d_col1:
        st.caption("Live attendance summary for today")
    with d_col2:
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div style="font-size: 0.85rem; color: #64748b; font-weight: 600;">TOTAL STRENGTH</div>
                <div style="font-size: 1.8rem; font-weight: 700; color: #0f172a; margin-top: 4px;">{total_strength}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with m2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div style="font-size: 0.85rem; color: #166534; font-weight: 600;">🟢 PRESENT</div>
                <div style="font-size: 1.8rem; font-weight: 700; color: #15803d; margin-top: 4px;">{present_count}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with m3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div style="font-size: 0.85rem; color: #991b1b; font-weight: 600;">🔴 ABSENT</div>
                <div style="font-size: 1.8rem; font-weight: 700; color: #b91c1c; margin-top: 4px;">{absent_count}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with m4:
        st.markdown(
            f"""
            <div class="metric-card">
                <div style="font-size: 0.85rem; color: #9a3412; font-weight: 600;">⏳ NOT MARKED</div>
                <div style="font-size: 1.8rem; font-weight: 700; color: #c2410c; margin-top: 4px;">{not_marked_count}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.write("")
    st.progress(min(percentage / 100, 1.0))
    st.markdown(f"**Overall Attendance Rate:** `{percentage:.2f}%` ({present_count} of {total_strength} present)")

    st.divider()
    st.subheader("📊 Branch-wise Breakdown")

    try:
        all_students_list = get_all_students()
        student_branch_map = {
            str(s["student_id"]): str(s.get("branch", "Unknown"))
            for s in all_students_list
        }
    except Exception as e:
        student_branch_map = {}

    branch_counts = {}
    branch_totals = {}

    for s in all_students_list:
        b = str(s.get("branch", "Unknown")).strip()
        if b:
            branch_totals[b] = branch_totals.get(b, 0) + 1

    for rec in today_records:
        if str(rec.get("status", "")).strip().lower() == "present":
            sid = str(rec.get("student_id"))
            b = student_branch_map.get(sid, "Unknown")
            branch_counts[b] = branch_counts.get(b, 0) + 1

    all_branches = sorted(list(set(list(branch_totals.keys()) + list(branch_counts.keys()))))

    if all_branches:
        b_cols = st.columns(min(len(all_branches), 5))
        for idx, br in enumerate(all_branches):
            col_target = b_cols[idx % min(len(all_branches), 5)]
            p_cnt = branch_counts.get(br, 0)
            t_cnt = branch_totals.get(br, 0)
            b_rate = (p_cnt / t_cnt * 100) if t_cnt > 0 else 0
            with col_target:
                st.metric(
                    f"Branch {br}",
                    f"{p_cnt} / {t_cnt}",
                    delta=f"{b_rate:.1f}%" if t_cnt > 0 else None
                )


# ------------------------------------------------------------
# TAB 2: BRANCH ATTENDANCE ENTRY
# ------------------------------------------------------------
with tab_branch:
    st.subheader("📝 Mark Attendance by Branch")
    st.caption("Select a branch to mark attendance. Select mode below to post either Absentees or Presentees.")

    try:
        all_students = get_all_students()
        branch_options = sorted(
            {str(s.get("branch", "")).strip() for s in all_students if str(s.get("branch", "")).strip()}
        )
    except Exception as e:
        all_students = []
        branch_options = []
        st.error(f"Error loading branches: {e}")

    if branch_options:
        c_sel, c_flt = st.columns([1, 2])
        with c_sel:
            selected_branch = st.selectbox("🎓 Select Branch", branch_options, key="branch_selector")
        with c_flt:
            filter_text = st.text_input("🔎 Filter student list", placeholder="Search name or ID within branch...", key="branch_filter")

        branch_students = [
            s for s in all_students
            if str(s.get("branch", "")).strip() == selected_branch
        ]
        branch_students = sorted(branch_students, key=lambda x: str(x.get("student_name", "")).lower())

        if filter_text.strip():
            ft = filter_text.strip().lower()
            branch_students = [
                s for s in branch_students
                if ft in str(s.get("student_name", "")).lower() or ft in str(s.get("student_id", "")).lower()
            ]

        branch_student_ids = {str(s["student_id"]) for s in branch_students}
        branch_attendance = {
            str(r["student_id"]): r for r in today_records if str(r.get("student_id")) in branch_student_ids
        }

        # Filter session selections to active branch
        st.session_state.selected_students = {
            sid for sid in st.session_state.selected_students if sid in branch_student_ids
        }

        # Select Mode: Post Only Absentees vs Post Only Present
        post_mode = st.radio(
            "Posting Mode Option:",
            ["Post Only Absentees (Selected = Absent, Rest = Present)", "Post Only Present (Selected = Present, Rest = Absent)"],
            horizontal=True
        )

        st.divider()

        already_present = 0
        already_absent = 0
        unmarked_count = 0

        checkbox_label = "Select Absent" if "Absentees" in post_mode else "Select Present"

        # Header Row
        h1, h2, h3, h4 = st.columns([1.2, 4, 2, 2])
        with h1: st.markdown("**Student ID**")
        with h2: st.markdown("**Student Name / Batch**")
        with h3: st.markdown("**Today's Status**")
        with h4: st.markdown(f"**{checkbox_label}**")

        st.divider()

        # Render Student Rows
        for student in branch_students:
            sid = str(student["student_id"])
            existing = branch_attendance.get(sid)
            is_active = student.get("active", True)

            r1, r2, r3, r4 = st.columns([1.2, 4, 2, 2])

            with r1:
                st.write(f"`{sid}`")

            with r2:
                st.markdown(f"**{student['student_name']}**  \n<span style='color: #64748b; font-size: 0.82rem;'>Batch {student['batch']}</span>", unsafe_allow_html=True)

            with r3:
                if not is_active:
                    st.markdown("<span class='status-badge badge-inactive'>Inactive</span>", unsafe_allow_html=True)
                elif existing:
                    st_val = str(existing.get("status", "")).strip().lower()
                    if st_val == "present":
                        already_present += 1
                        st.markdown("<span class='status-badge badge-present'>Present</span>", unsafe_allow_html=True)
                    elif st_val == "absent":
                        already_absent += 1
                        st.markdown("<span class='status-badge badge-absent'>Absent</span>", unsafe_allow_html=True)
                    else:
                        unmarked_count += 1
                        st.markdown("<span class='status-badge badge-pending'>Not Marked</span>", unsafe_allow_html=True)
                else:
                    unmarked_count += 1
                    st.markdown("<span class='status-badge badge-pending'>Not Marked</span>", unsafe_allow_html=True)

            with r4:
                if not is_active:
                    st.checkbox(checkbox_label, value=False, disabled=True, key=f"dis_{selected_branch}_{sid}")
                else:
                    is_selected = sid in st.session_state.selected_students
                    checked = st.checkbox(checkbox_label, value=is_selected, key=f"chk_{selected_branch}_{sid}")
                    if checked:
                        st.session_state.selected_students.add(sid)
                    else:
                        st.session_state.selected_students.discard(sid)

        st.divider()

        # Calculate counts based on selection mode
        active_branch_students = [s for s in branch_students if s.get("active", True)]
        selected_ids = {sid for sid in st.session_state.selected_students if sid in branch_student_ids}

        if "Absentees" in post_mode:
            target_absents = len(selected_ids)
            target_presents = len(active_branch_students) - target_absents
        else:
            target_presents = len(selected_ids)
            target_absents = len(active_branch_students) - target_presents

        b_sum1, b_sum2, b_sum3, b_sum4 = st.columns(4)
        with b_sum1: st.metric("Total Active in Branch", len(active_branch_students))
        with b_sum2: st.metric("Will Mark Present", target_presents)
        with b_sum3: st.metric("Will Mark Absent", target_absents)
        with b_sum4: st.metric("Selected Checkboxes", len(selected_ids))

        btn_label = f"⚡ Submit Attendance ({target_presents} Present, {target_absents} Absent)"

        if st.button(
            btn_label,
            type="primary",
            use_container_width=True,
            disabled=len(active_branch_students) == 0
        ):
            bulk_payload = []

            for s in active_branch_students:
                sid = str(s["student_id"])
                
                if "Absentees" in post_mode:
                    status = "Absent" if sid in selected_ids else "Present"
                else:
                    status = "Present" if sid in selected_ids else "Absent"

                bulk_payload.append({
                    "student_id": int(sid) if sid.isdigit() else sid,
                    "attendance_date": today,
                    "status": status,
                    "marked_by": faculty_name,
                    "marked_at": current_time
                })

            with st.spinner("Saving complete branch attendance..."):
                try:
                    save_bulk_attendance(bulk_payload)
                    st.session_state.selected_students.clear()
                    st.success(f"✅ Attendance saved! ({target_presents} Present, {target_absents} Absent).")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to submit attendance: {e}")
    else:
        st.warning("No branch data found in student records.")


# ------------------------------------------------------------
# TAB 3: INDIVIDUAL STUDENT SEARCH
# ------------------------------------------------------------
with tab_search:
    st.subheader("🔍 Individual Student Search & Quick Edit")
    st.caption("Search for any student by Name or ID to view or modify today's status.")

    search_text = st.text_input(
        "Enter Student Name or Roll / Student ID",
        placeholder="e.g. KARANAM or 706",
        key="global_search_input"
    )

    if search_text.strip():
        try:
            matched_students = search_students(search_text)
        except Exception as e:
            matched_students = []
            st.error(f"Search error: {e}")

        if not matched_students:
            st.warning("❌ No matching students found.")
        else:
            st.success(f"Found {len(matched_students)} student(s)")
            
            student_dict = {
                f"{s['student_id']} - {s['student_name']} ({s['branch']} | Batch {s['batch']})": s
                for s in matched_students
            }
            
            selected_key = st.selectbox("Select Student", list(student_dict.keys()))
            target_student = student_dict[selected_key]
            target_id = target_student["student_id"]

            st.write("---")
            st.markdown(f"### **{target_student['student_name']}**")
            st.markdown(f"**ID:** `{target_student['student_id']}` | **Branch:** {target_student['branch']} | **Batch:** {target_student['batch']}")

            existing_record = get_student_attendance(target_id)

            if existing_record:
                curr_status = existing_record.get("status", "Not Marked")
                st.info(f"Today's Status: **{curr_status}** (Marked by: {existing_record.get('marked_by', 'N/A')})")

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("🟢 Set to PRESENT", type="primary", use_container_width=True):
                        try:
                            update_attendance(target_id, "Present", faculty_name)
                            st.toast("Status updated to PRESENT", icon="✅")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Update failed: {e}")
                with c2:
                    if st.button("🔴 Set to ABSENT", use_container_width=True):
                        try:
                            update_attendance(target_id, "Absent", faculty_name)
                            st.toast("Status updated to ABSENT", icon="🔴")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Update failed: {e}")
            else:
                st.warning("Status for today: **Not Marked**")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("🟢 Mark PRESENT", type="primary", use_container_width=True):
                        try:
                            save_attendance(target_id, "Present", faculty_name)
                            st.toast("Marked PRESENT", icon="✅")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Save failed: {e}")
                with c2:
                    if st.button("🔴 Mark ABSENT", use_container_width=True):
                        try:
                            save_attendance(target_id, "Absent", faculty_name)
                            st.toast("Marked ABSENT", icon="🔴")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Save failed: {e}")


# ------------------------------------------------------------
# TAB 4: REPORTS AND EXPORTS
# ------------------------------------------------------------
with tab_reports:
    st.subheader("📈 Attendance Analytics & Report Export")
    st.write("Generate and download complete continuous attendance matrices from Day 1 to today.")

    if st.button("📊 Generate Complete Attendance Report", type="primary", use_container_width=True):
        with st.spinner("Generating complete historical matrix..."):
            try:
                report_df = get_complete_attendance_report()
                st.session_state.report_df = report_df
            except Exception as e:
                st.error(f"Error generating report: {e}")
                st.session_state.report_df = None

    if st.session_state.report_df is not None:
        report_df = st.session_state.report_df

        if report_df.empty:
            st.warning("No data available to display.")
        else:
            st.success(f"Report ready! Contains {len(report_df)} student records.")
            
            with st.expander("👁️ Preview Full Report Table", expanded=True):
                st.dataframe(report_df, use_container_width=True, hide_index=True)

            d_col1, d_col2 = st.columns(2)
            
            with d_col1:
                try:
                    excel_data = create_branch_wise_excel(report_df)
                    st.download_button(
                        label="📥 Download Excel Workbook (Sheet per Branch)",
                        data=excel_data,
                        file_name=f"complete_attendance_{today}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"Error creating Excel workbook: {e}")

            with d_col2:
                csv_data = report_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Download Complete CSV",
                    data=csv_data,
                    file_name=f"complete_attendance_{today}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
