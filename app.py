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
# SUPABASE CONNECTION
# ============================================================

@st.cache_resource
def get_supabase():

    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )


supabase = get_supabase()


# ============================================================
# INDIA DATE / TIME
# ============================================================

india_time = datetime.now(
    ZoneInfo("Asia/Kolkata")
)

today = india_time.date().isoformat()
current_time = india_time.isoformat()


# ============================================================
# SESSION STATE
# ============================================================

if "faculty_name" not in st.session_state:
    st.session_state.faculty_name = ""

if "report_df" not in st.session_state:
    st.session_state.report_df = None


# ============================================================
# GET TOTAL STUDENT STRENGTH
# ============================================================

def get_total_strength():

    response = (
        supabase
        .table("students")
        .select(
            "student_id",
            count="exact"
        )
        .execute()
    )

    return response.count or 0


# ============================================================
# GET ALL STUDENTS - PAGINATED
# ============================================================

def get_all_students():

    all_students = []

    start = 0
    page_size = 1000

    while True:

        response = (
            supabase
            .table("students")
            .select(
                "student_id, student_name, branch, batch"
            )
            .range(
                start,
                start + page_size - 1
            )
            .execute()
        )

        batch = response.data or []

        all_students.extend(batch)

        if len(batch) < page_size:
            break

        start += page_size

    return all_students


# ============================================================
# GET TODAY'S ATTENDANCE - PAGINATED
# ============================================================

def get_today_attendance():

    all_records = []

    start = 0
    page_size = 1000

    while True:

        response = (
            supabase
            .table("attendance")
            .select(
                "student_id, attendance_date, status, "
                "marked_by, marked_at"
            )
            .eq(
                "attendance_date",
                today
            )
            .range(
                start,
                start + page_size - 1
            )
            .execute()
        )

        batch = response.data or []

        all_records.extend(batch)

        if len(batch) < page_size:
            break

        start += page_size

    return all_records


# ============================================================
# SEARCH STUDENTS
# ============================================================

def search_students(search_text):

    search_text = search_text.strip()

    if not search_text:
        return []


    # --------------------------------------------------------
    # Search by Student Name
    # --------------------------------------------------------

    response = (
        supabase
        .table("students")
        .select(
            "student_id, student_name, branch, batch"
        )
        .ilike(
            "student_name",
            f"%{search_text}%"
        )
        .limit(20)
        .execute()
    )

    students = response.data or []


    # --------------------------------------------------------
    # If no name result, search Student ID
    # --------------------------------------------------------

    if not students:

        try:

            numeric_id = int(search_text)

            response = (
                supabase
                .table("students")
                .select(
                    "student_id, student_name, branch, batch"
                )
                .eq(
                    "student_id",
                    numeric_id
                )
                .limit(20)
                .execute()
            )

            students = response.data or []

        except ValueError:

            response = (
                supabase
                .table("students")
                .select(
                    "student_id, student_name, branch, batch"
                )
                .ilike(
                    "student_id",
                    f"%{search_text}%"
                )
                .limit(20)
                .execute()
            )

            students = response.data or []


    return students


# ============================================================
# GET INDIVIDUAL STUDENT'S TODAY ATTENDANCE
# ============================================================

def get_student_attendance(student_id):

    response = (
        supabase
        .table("attendance")
        .select(
            "student_id, attendance_date, status, "
            "marked_by, marked_at"
        )
        .eq(
            "student_id",
            student_id
        )
        .eq(
            "attendance_date",
            today
        )
        .limit(1)
        .execute()
    )

    records = response.data or []

    if records:
        return records[0]

    return None


# ============================================================
# SAVE ATTENDANCE
# ============================================================

def save_attendance(
    student_id,
    status,
    faculty_name
):

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
        .upsert(
            data,
            on_conflict="student_id,attendance_date"
        )
        .execute()
    )


# ============================================================
# UPDATE ATTENDANCE
# ============================================================

def update_attendance(
    student_id,
    status,
    faculty_name
):

    return (
        supabase
        .table("attendance")
        .update(
            {
                "status": status,
                "marked_by": faculty_name,
                "marked_at": current_time
            }
        )
        .eq(
            "student_id",
            student_id
        )
        .eq(
            "attendance_date",
            today
        )
        .execute()
    )


# ============================================================
# GET ALL ATTENDANCE - PAGINATED
# ============================================================

def get_all_attendance():
    """
    Get the complete attendance history from Supabase.
    Uses pagination so the Supabase/PostgREST 1000-row limit
    does not truncate the report.
    """
    all_records = []

    start = 0
    page_size = 1000

    while True:
        response = (
            supabase
            .table("attendance")
            .select(
                "student_id, attendance_date, status, "
                "marked_by, marked_at"
            )
            .order("attendance_date")
            .order("student_id")
            .range(
                start,
                start + page_size - 1
            )
            .execute()
        )

        batch = response.data or []
        all_records.extend(batch)

        if len(batch) < page_size:
            break

        start += page_size

    return all_records


# ============================================================
# BUILD COMPLETE ATTENDANCE HISTORY REPORT
# ============================================================

def get_complete_attendance_report():
    """
    Build a continuous attendance report from the first
    attendance date through today.

    Every student from the students table is included.
    If a student has no attendance record for a date,
    that date is shown as Absent.
    """

    students = get_all_students()
    attendance = get_all_attendance()

    if not students:
        return pd.DataFrame()

    students_df = pd.DataFrame(students)

    # If there are no attendance records yet, return the
    # student list only. No date columns can be generated.
    if not attendance:
        return students_df[
            ["student_id", "student_name", "branch", "batch"]
        ].rename(
            columns={
                "student_id": "Student ID",
                "student_name": "Student Name",
                "branch": "Branch",
                "batch": "Batch"
            }
        )

    attendance_df = pd.DataFrame(attendance)

    attendance_df["attendance_date"] = pd.to_datetime(
        attendance_df["attendance_date"],
        errors="coerce"
    ).dt.date

    attendance_df = attendance_df.dropna(
        subset=["attendance_date"]
    )

    if attendance_df.empty:
        return students_df[
            ["student_id", "student_name", "branch", "batch"]
        ].rename(
            columns={
                "student_id": "Student ID",
                "student_name": "Student Name",
                "branch": "Branch",
                "batch": "Batch"
            }
        )

    # First attendance date is Day 1. Continue through today.
    first_date = min(attendance_df["attendance_date"])
    last_date = india_time.date()

    all_dates = pd.date_range(
        start=first_date,
        end=last_date,
        freq="D"
    ).date

    # If duplicate attendance rows somehow exist for a student/date,
    # keep the last returned record.
    attendance_df = (
        attendance_df
        .drop_duplicates(
            subset=["student_id", "attendance_date"],
            keep="last"
        )
    )

    attendance_pivot = (
        attendance_df
        .pivot(
            index="student_id",
            columns="attendance_date",
            values="status"
        )
        .reindex(columns=all_dates)
        .reset_index()
    )

    # Merge with the complete student master list.
    # Therefore even students with no attendance records appear.
    report = students_df.merge(
        attendance_pivot,
        on="student_id",
        how="left"
    )

    # Every missing attendance record = Absent.
    date_columns = [
        col for col in report.columns
        if isinstance(col, date)
    ]

    for col in date_columns:
        report[col] = (
            report[col]
            .fillna("Absent")
            .replace("", "Absent")
        )

    # Sort branch-wise, then student name.
    report = report.sort_values(
        by=["branch", "student_name"],
        kind="stable"
    )

    # Rename fixed columns and date columns for the report.
    rename_columns = {
        "student_id": "Student ID",
        "student_name": "Student Name",
        "branch": "Branch",
        "batch": "Batch"
    }

    for col in date_columns:
        rename_columns[col] = col.strftime("%d-%m-%Y")

    report = report.rename(columns=rename_columns)

    # Keep student details first, followed by dates.
    fixed_columns = [
        "Student ID",
        "Student Name",
        "Branch",
        "Batch"
    ]

    date_column_names = [
        d.strftime("%d-%m-%Y")
        for d in all_dates
    ]

    report = report[
        fixed_columns + date_column_names
    ]

    return report


# ============================================================
# CREATE BRANCH-WISE EXCEL WORKBOOK
# ============================================================

def create_branch_wise_excel(report_df):
    """
    Create one Excel sheet per branch plus a Summary sheet.
    """

    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        # ----------------------------------------------------
        # SUMMARY SHEET
        # ----------------------------------------------------
        date_columns = [
            col for col in report_df.columns
            if col not in [
                "Student ID",
                "Student Name",
                "Branch",
                "Batch"
            ]
        ]

        summary_rows = []

        for branch, branch_df in report_df.groupby(
            "Branch",
            sort=True
        ):

            total_students = len(branch_df)

            # Total Present across all student/date cells.
            total_present = sum(
                (
                    branch_df[date_columns]
                    .astype(str)
                    .apply(
                        lambda col:
                        col.str.strip().str.lower() == "present"
                    )
                    .sum()
                )
            )

            total_possible = (
                total_students * len(date_columns)
            )

            percentage = (
                (total_present / total_possible) * 100
                if total_possible > 0
                else 0
            )

            summary_rows.append(
                {
                    "Branch": branch,
                    "Total Students": total_students,
                    "Total Present": int(total_present),
                    "Total Attendance Entries": total_possible,
                    "Attendance %": round(
                        percentage,
                        2
                    )
                }
            )

        summary_df = pd.DataFrame(summary_rows)

        if not summary_df.empty:
            summary_df.to_excel(
                writer,
                index=False,
                sheet_name="Summary"
            )

        # ----------------------------------------------------
        # ONE SHEET FOR EACH BRANCH
        # ----------------------------------------------------
        for branch, branch_df in report_df.groupby(
            "Branch",
            sort=True
        ):

            # Excel sheet names cannot exceed 31 characters.
            # Also remove characters Excel does not allow.
            safe_sheet_name = str(branch)

            for char in [
                "\\", "/", "*", "[", "]", ":", "?"
            ]:
                safe_sheet_name = safe_sheet_name.replace(
                    char,
                    "_"
                )

            safe_sheet_name = (
                safe_sheet_name[:31] or "Branch"
            )

            branch_df.to_excel(
                writer,
                index=False,
                sheet_name=safe_sheet_name
            )

        # ----------------------------------------------------
        # FORMATTING
        # ----------------------------------------------------
        workbook = writer.book

        for worksheet in workbook.worksheets:

            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = (
                worksheet.dimensions
            )

            # Bold header
            for cell in worksheet[1]:
                cell.font = cell.font.copy(
                    bold=True
                )

            # Reasonable column widths
            for column_cells in worksheet.columns:

                column_letter = (
                    column_cells[0].column_letter
                )

                max_length = 0

                for cell in column_cells:
                    value = "" if cell.value is None else str(
                        cell.value
                    )
                    max_length = max(
                        max_length,
                        len(value)
                    )

                worksheet.column_dimensions[
                    column_letter
                ].width = min(
                    max(max_length + 2, 12),
                    30
                )

    return output.getvalue()


# ============================================================
# BUILD COMPLETE TODAY REPORT
# ============================================================

def get_full_today_report():

    # --------------------------------------------------------
    # Get ALL students, including >1000
    # --------------------------------------------------------

    students = get_all_students()


    # --------------------------------------------------------
    # Get ALL attendance records for today
    # --------------------------------------------------------

    attendance = get_today_attendance()


    # --------------------------------------------------------
    # Attendance lookup
    # --------------------------------------------------------

    attendance_map = {}

    for record in attendance:

        attendance_map[
            str(record["student_id"])
        ] = record


    # --------------------------------------------------------
    # Build report
    # --------------------------------------------------------

    report = []

    for student in students:

        student_key = str(
            student["student_id"]
        )

        record = attendance_map.get(
            student_key
        )


        if record:

            status = record.get(
                "status",
                ""
            )

            attendance_date = record.get(
                "attendance_date",
                today
            )

            marked_by = record.get(
                "marked_by",
                ""
            )

            marked_at = record.get(
                "marked_at",
                ""
            )

        else:

            status = "Not Marked"
            attendance_date = today
            marked_by = ""
            marked_at = ""


        report.append(
            {
                "Student ID":
                    student["student_id"],

                "Student Name":
                    student["student_name"],

                "Branch":
                    student["branch"],

                "Batch":
                    student["batch"],

                "Attendance Date":
                    attendance_date,

                "Status":
                    status,

                "Marked By":
                    marked_by,

                "Marked At":
                    marked_at
            }
        )


    return pd.DataFrame(
        report,
        columns=[
            "Student ID",
            "Student Name",
            "Branch",
            "Batch",
            "Attendance Date",
            "Status",
            "Marked By",
            "Marked At"
        ]
    )


# ============================================================
# HEADER
# ============================================================

st.title("📋 College Attendance System")

st.caption(
    f"Attendance Date: "
    f"{india_time.strftime('%d-%m-%Y')}"
)


# ============================================================
# FACULTY NAME - ONE TIME PER SESSION
# ============================================================

if not st.session_state.faculty_name:

    st.subheader("👨‍🏫 Faculty Login")

    faculty_input = st.text_input(
        "Enter Faculty Name",
        placeholder="Example: Dr. S. Kumar"
    )


    if st.button(
        "Continue",
        type="primary",
        use_container_width=True
    ):

        if faculty_input.strip():

            st.session_state.faculty_name = (
                faculty_input.strip()
            )

            st.rerun()

        else:

            st.warning(
                "Please enter Faculty Name."
            )


    st.stop()


# ============================================================
# SHOW FACULTY NAME
# ============================================================

faculty_col1, faculty_col2 = st.columns(
    [5, 1]
)

with faculty_col1:

    st.success(
        f"👨‍🏫 Faculty: "
        f"**{st.session_state.faculty_name}**"
    )


with faculty_col2:

    if st.button(
        "Change Faculty",
        use_container_width=True
    ):

        st.session_state.faculty_name = ""

        st.rerun()


faculty_name = st.session_state.faculty_name


st.divider()


# ============================================================
# DASHBOARD
# ============================================================

st.subheader("📊 Today's Attendance")

if st.button(
    "🔄 Refresh Dashboard",
    use_container_width=False
):
    st.rerun()

# ------------------------------------------------------------
# Total strength - live from Supabase
# ------------------------------------------------------------
try:
    total_strength = get_total_strength()
except Exception as e:
    st.error(f"Unable to get total student strength: {e}")
    total_strength = 0

# ------------------------------------------------------------
# Today's attendance - live from Supabase
# ------------------------------------------------------------
try:
    today_records = get_today_attendance()
except Exception as e:
    st.error(f"Unable to get today's attendance: {e}")
    today_records = []

# ------------------------------------------------------------
# Count present / absent
# ------------------------------------------------------------
present_count = sum(
    1 for record in today_records
    if str(record.get("status", "")).strip().lower() == "present"
)

absent_count = sum(
    1 for record in today_records
    if str(record.get("status", "")).strip().lower() == "absent"
)

not_marked_count = max(
    0,
    total_strength - present_count - absent_count
)

# ============================================================
# MAIN DASHBOARD METRICS
# ============================================================

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("👥 Total Strength", total_strength)

with col2:
    st.metric("🟢 Present", f"{present_count} / {total_strength}")

with col3:
    st.metric("🔴 Absent", absent_count)

with col4:
    st.metric("⏳ Not Marked", not_marked_count)

# ============================================================
# PRESENT PERCENTAGE
# ============================================================

percentage = (
    present_count / total_strength * 100
    if total_strength > 0 else 0
)

st.progress(min(percentage / 100, 1.0))

st.markdown(
    f"**🟢 TOTAL PRESENT: {present_count} / {total_strength} "
    f"({percentage:.2f}%)**"
)

# ============================================================
# BATCH-WISE PRESENT
# ============================================================

st.subheader("📊 Batch-wise Present")

# Student → Batch mapping is cached for 60 seconds so the
# dashboard remains fast while still allowing periodic updates.
@st.cache_data(ttl=60, show_spinner=False)
def get_student_batch_map():
    students = get_all_students()
    return {
        str(student["student_id"]): str(student["batch"])
        for student in students
    }

try:
    student_batch_map = get_student_batch_map()
except Exception as e:
    student_batch_map = {}
    st.error(f"Unable to load batch information: {e}")

batch_present = {}

for record in today_records:
    if str(record.get("status", "")).strip().lower() == "present":
        student_id_key = str(record.get("student_id"))
        batch = student_batch_map.get(student_id_key, "Unknown")
        batch_present[batch] = batch_present.get(batch, 0) + 1

batch_order = ["A", "1", "B", "2", "C", "3", "D", "4"]

batch_columns = st.columns(len(batch_order))

for column, batch in zip(batch_columns, batch_order):
    with column:
        st.metric(
            f"Batch {batch}",
            batch_present.get(batch, 0)
        )

# Show any unexpected batch values rather than silently losing them.
unknown_present = batch_present.get("Unknown", 0)
if unknown_present:
    st.warning(
        f"⚠️ {unknown_present} present student(s) could not be matched to a batch."
    )

st.markdown(
    f"### 🟢 **TOTAL PRESENT: {present_count} / {total_strength}**"
)

st.divider()

# ============================================================
# BRANCH-WISE ATTENDANCE ENTRY
# ============================================================

st.subheader("📝 Mark Attendance by Branch")

st.caption(
    "Select a branch. All students in that branch will appear below. "
    "Tick PRESENT for the required students and submit all selected students together."
)

# ------------------------------------------------------------
# Load branches from the student master table
# ------------------------------------------------------------
try:
    all_students_for_branch = get_all_students()
    branch_values = sorted(
        {
            str(student.get("branch", "")).strip()
            for student in all_students_for_branch
            if str(student.get("branch", "")).strip()
        }
    )
except Exception as e:
    all_students_for_branch = []
    branch_values = []
    st.error(f"Unable to load branch information: {e}")

if branch_values:
    selected_branch = st.selectbox(
        "🎓 Select Branch",
        branch_values,
        key="attendance_branch"
    )

    branch_students = [
        student
        for student in all_students_for_branch
        if str(student.get("branch", "")).strip() == selected_branch
    ]

    branch_students = sorted(
        branch_students,
        key=lambda x: str(x.get("student_name", "")).lower()
    )

    branch_student_ids = {
        str(student["student_id"])
        for student in branch_students
    }

    # today_records is already loaded by the dashboard above.
    # Reuse it instead of querying Supabase for every student.
    branch_attendance = {
        str(record["student_id"]): record
        for record in today_records
        if str(record.get("student_id")) in branch_student_ids
    }

    if "selected_present_students" not in st.session_state:
        st.session_state.selected_present_students = set()

    # Keep only selections belonging to the current branch.
    st.session_state.selected_present_students = {
        sid
        for sid in st.session_state.selected_present_students
        if sid in branch_student_ids
    }

    st.markdown(
        f"### {selected_branch} — {len(branch_students)} Students"
    )

    already_present = 0
    already_absent = 0
    not_marked = 0

    # --------------------------------------------------------
    # Student list
    # --------------------------------------------------------
    for student in branch_students:
        sid = str(student["student_id"])
        existing = branch_attendance.get(sid)

        if existing:
            status = str(existing.get("status", "")).strip().lower()

            if status == "present":
                already_present += 1
                status_text = "🟢 Present"
                default_value = True
                disabled = True
            elif status == "absent":
                already_absent += 1
                status_text = "🔴 Absent"
                default_value = False
                disabled = True
            else:
                not_marked += 1
                status_text = "⏳ Not Marked"
                default_value = False
                disabled = False
        else:
            not_marked += 1
            status_text = "⏳ Not Marked"
            default_value = sid in st.session_state.selected_present_students
            disabled = False

        row1, row2, row3, row4 = st.columns([0.9, 4.5, 1.3, 1.2])

        with row1:
            st.write(f"**{student['student_id']}**")

        with row2:
            st.write(
                f"**{student['student_name']}**  \n"
                f"Batch {student['batch']}"
            )

        with row3:
            st.write(status_text)

        with row4:
            if disabled:
                st.checkbox(
                    "Present",
                    value=default_value,
                    disabled=True,
                    key=f"present_done_{selected_branch}_{sid}"
                )
            else:
                checked = st.checkbox(
                    "Present",
                    value=default_value,
                    key=f"present_select_{selected_branch}_{sid}"
                )

                if checked:
                    st.session_state.selected_present_students.add(sid)
                else:
                    st.session_state.selected_present_students.discard(sid)

    st.divider()

    selected_ids = [
        sid
        for sid in st.session_state.selected_present_students
        if sid in branch_student_ids
        and sid not in branch_attendance
    ]

    sum1, sum2, sum3, sum4 = st.columns(4)

    with sum1:
        st.metric("👥 Branch Strength", len(branch_students))

    with sum2:
        st.metric("🟢 Already Present", already_present)

    with sum3:
        st.metric("🔴 Already Absent", already_absent)

    with sum4:
        st.metric("☑️ Selected Now", len(selected_ids))

    st.write("")

    if st.button(
        f"💾 Submit {len(selected_ids)} Present Student(s)",
        type="primary",
        use_container_width=True,
        disabled=len(selected_ids) == 0
    ):
        success_count = 0
        failed_students = []

        with st.spinner(
            f"Saving attendance for {len(selected_ids)} student(s)..."
        ):
            for sid in selected_ids:
                try:
                    original_student = next(
                        s for s in branch_students
                        if str(s["student_id"]) == sid
                    )

                    save_attendance(
                        original_student["student_id"],
                        "Present",
                        faculty_name
                    )
                    success_count += 1

                except Exception as e:
                    failed_students.append((sid, str(e)))

        for sid in selected_ids:
            if not any(
                failed_sid == sid
                for failed_sid, _ in failed_students
            ):
                st.session_state.selected_present_students.discard(sid)

        if success_count:
            st.success(
                f"✅ Attendance submitted successfully for "
                f"{success_count} student(s)."
            )

        if failed_students:
            st.error(
                f"❌ {len(failed_students)} student(s) could not be saved."
            )
            for sid, error in failed_students:
                st.write(f"Student ID {sid}: {error}")

        # Intentionally no st.rerun().
        # Faculty can continue working without an automatic refresh.

else:
    st.warning("No branches found in the student table.")


# ============================================================
# OPTIONAL INDIVIDUAL STUDENT SEARCH
# ============================================================

with st.expander("🔎 Search Individual Student", expanded=False):

    search_text = st.text_input(
        "Search by Student Name or Student ID",
        placeholder="Example: KARANAM or 706",
        key="individual_student_search"
    )

    if search_text.strip():

        try:
            students = search_students(search_text)
        except Exception as e:
            students = []
            st.error(f"Search error: {e}")

        if not students:
            st.warning("❌ No student found.")

        else:
            st.success(f"✅ {len(students)} student(s) found.")

            student_options = {}

            for student in students:
                label = (
                    f"{student['student_id']} | "
                    f"{student['student_name']} | "
                    f"{student['branch']} | "
                    f"Batch {student['batch']}"
                )

                student_options[label] = student

            selected_label = st.selectbox(
                "Select Student",
                list(student_options.keys())
            )

            selected_student = student_options[selected_label]
            student_id = selected_student["student_id"]

            st.write(
                f"**{selected_student['student_name']}** | "
                f"{selected_student['branch']} | "
                f"Batch {selected_student['batch']}"
            )

            existing = get_student_attendance(student_id)

            if existing:

                st.info(
                    f"Today's status: **{existing.get('status')}**"
                )

                change1, change2 = st.columns(2)

                with change1:
                    if st.button(
                        "🟢 Change to PRESENT",
                        type="primary",
                        use_container_width=True
                    ):
                        try:
                            update_attendance(
                                student_id,
                                "Present",
                                faculty_name
                            )
                            st.success("Attendance changed to PRESENT.")
                        except Exception as e:
                            st.error(f"Unable to update: {e}")

                with change2:
                    if st.button(
                        "🔴 Change to ABSENT",
                        use_container_width=True
                    ):
                        try:
                            update_attendance(
                                student_id,
                                "Absent",
                                faculty_name
                            )
                            st.success("Attendance changed to ABSENT.")
                        except Exception as e:
                            st.error(f"Unable to update: {e}")

            else:

                mark1, mark2 = st.columns(2)

                with mark1:
                    if st.button(
                        "🟢 PRESENT",
                        type="primary",
                        use_container_width=True
                    ):
                        try:
                            save_attendance(
                                student_id,
                                "Present",
                                faculty_name
                            )
                            st.success("Attendance marked PRESENT.")
                        except Exception as e:
                            st.error(f"Unable to save attendance: {e}")

                with mark2:
                    if st.button(
                        "🔴 ABSENT",
                        use_container_width=True
                    ):
                        try:
                            save_attendance(
                                student_id,
                                "Absent",
                                faculty_name
                            )
                            st.success("Attendance marked ABSENT.")
                        except Exception as e:
                            st.error(f"Unable to save attendance: {e}")

# ============================================================
# COMPLETE ATTENDANCE REPORT
# ============================================================

st.divider()

st.subheader(
    "📋 Complete Attendance Report"
)

st.write(
    "Generate attendance from Day 1 to today. "
    "Every student is included and a missing attendance "
    "record is treated as Absent."
)


if st.button(
    "📊 Generate Complete Attendance Report",
    use_container_width=True
):

    with st.spinner(
        "Loading all students and attendance history..."
    ):

        try:

            report_df = get_complete_attendance_report()

            st.session_state.report_df = report_df

        except Exception as e:

            st.error(
                f"Unable to create complete report: {e}"
            )

            st.session_state.report_df = None


# ============================================================
# DISPLAY COMPLETE REPORT
# ============================================================

if st.session_state.report_df is not None:

    report_df = st.session_state.report_df

    if report_df.empty:

        st.warning(
            "No student data available."
        )

    else:

        st.success(
            f"✅ Complete report loaded: "
            f"{len(report_df)} students"
        )

        st.dataframe(
            report_df,
            use_container_width=True,
            hide_index=True
        )

        # ----------------------------------------------------
        # BRANCH-WISE EXCEL
        # ----------------------------------------------------
        try:

            excel_data = create_branch_wise_excel(
                report_df
            )

            st.download_button(
                label=(
                    "📥 Download Branch-wise Excel "
                    "(One Sheet per Branch)"
                ),
                data=excel_data,
                file_name=(
                    f"complete_attendance_"
                    f"{today}.xlsx"
                ),
                mime=(
                    "application/vnd.openxmlformats-"
                    "officedocument.spreadsheetml.sheet"
                ),
                use_container_width=True
            )

        except Exception as e:

            st.error(
                f"Unable to create Excel file: {e}"
            )

        # ----------------------------------------------------
        # COMPLETE CSV
        # ----------------------------------------------------
        csv_data = (
            report_df
            .to_csv(index=False)
            .encode("utf-8")
        )

        st.download_button(
            label="📥 Download Complete Attendance CSV",
            data=csv_data,
            file_name=(
                f"complete_attendance_{today}.csv"
            ),
            mime="text/csv",
            use_container_width=True
        )
        
