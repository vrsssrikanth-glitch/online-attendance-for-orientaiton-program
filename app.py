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

    # --------------------------------------------------------
    # Get today's attendance once for the selected branch.
    # This avoids a separate Supabase request for every student.
    # --------------------------------------------------------
    branch_student_ids = {
        str(student["student_id"])
        for student in branch_students
    }

    branch_attendance = {
        str(record["student_id"]): record
        for record in today_records
        if str(record.get("student_id")) in branch_student_ids
    }

    # Keep checkbox selections in session state.
    if "selected_present_students" not in st.session_state:
        st.session_state.selected_present_students = set()

    # Remove selections belonging to students no longer in the
    # currently displayed branch.
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
        sid for sid in st.session_state.selected_present_students
        if sid in branch_student_ids
        and sid not in branch_attendance
    ]

    # --------------------------------------------------------
    # Summary before submission
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # ONE-TIME MULTIPLE SUBMISSION
    # --------------------------------------------------------
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
                    save_attendance(
                        int(sid) if sid.isdigit() else sid,
                        "Present",
                        faculty_name
                    )
                    success_count += 1
                except Exception as e:
                    failed_students.append((sid, str(e)))

        # Clear only successfully submitted selections.
        for sid in selected_ids:
            if not any(failed_sid == sid for failed_sid, _ in failed_students):
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

        # No st.rerun() here.
        # The dashboard can be refreshed separately when required.
        st.session_state["attendance_submit_message"] = True

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
                current_status = str(
                    existing.get("status", "")
                ).strip().lower()

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
