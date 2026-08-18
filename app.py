import streamlit as st
from supabase import create_client
from datetime import datetime
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

    st.session_state.report_df = None

    st.rerun()
col1, col2, col3, col4 = st.columns(4)
# ============================================================
# BATCH-WISE PRESENT COUNT
# ============================================================

st.subheader("📊 Batch-wise Present")


# ------------------------------------------------------------
# Create student ID → batch lookup
# ------------------------------------------------------------

try:

    all_students_for_batch = get_all_students()

    student_batch_map = {
        str(student["student_id"]): student["batch"]
        for student in all_students_for_batch
    }

except Exception as e:

    student_batch_map = {}

    st.error(
        f"Unable to load batch information: {e}"
    )


# ------------------------------------------------------------
# Count PRESENT students batch-wise
# ------------------------------------------------------------

batch_present = {}

for record in today_records:

    status = str(
        record.get("status", "")
    ).lower()

    if status == "present":

        student_id_key = str(
            record["student_id"]
        )

        batch = student_batch_map.get(
            student_id_key,
            "Unknown"
        )

        batch_present[batch] = (
            batch_present.get(batch, 0) + 1
        )


# ------------------------------------------------------------
# Display batches in fixed order
# ------------------------------------------------------------

batch_order = [
    "A",
    "1",
    "B",
    "2",
    "C",
    "3",
    "D",
    "4"
]


batch_columns = st.columns(
    len(batch_order)
)


for column, batch in zip(
    batch_columns,
    batch_order
):

    with column:

        count = batch_present.get(
            batch,
            0
        )

        st.metric(
            f"Batch {batch}",
            count
        )


# ------------------------------------------------------------
# Total Present
# ------------------------------------------------------------

st.markdown(
    f"""
    ### 🟢 **TOTAL PRESENT: {present_count} / {total_strength}**
    """
)


# ------------------------------------------------------------
# Total strength
# ------------------------------------------------------------

try:

    total_strength = get_total_strength()

except Exception as e:

    st.error(
        f"Unable to get total student strength: {e}"
    )

    total_strength = 0


# ------------------------------------------------------------
# Today's attendance
# ------------------------------------------------------------

try:

    today_records = get_today_attendance()

except Exception as e:

    st.error(
        f"Unable to get today's attendance: {e}"
    )

    today_records = []


# ------------------------------------------------------------
# Count present / absent
# ------------------------------------------------------------

present_count = sum(
    1
    for record in today_records
    if str(
        record.get("status", "")
    ).lower() == "present"
)


absent_count = sum(
    1
    for record in today_records
    if str(
        record.get("status", "")
    ).lower() == "absent"
)


not_marked_count = max(
    0,
    total_strength
    - present_count
    - absent_count
)


# ============================================================
# DASHBOARD METRICS
# ============================================================

col1, col2, col3, col4 = st.columns(4)


with col1:

    st.metric(
        "👥 Total Strength",
        total_strength
    )


with col2:

    st.metric(
        "🟢 Present",
        f"{present_count} / {total_strength}"
    )


with col3:

    st.metric(
        "🔴 Absent",
        absent_count
    )


with col4:

    st.metric(
        "⏳ Not Marked",
        not_marked_count
    )


# ============================================================
# PRESENT PERCENTAGE
# ============================================================

if total_strength > 0:

    percentage = (
        present_count
        / total_strength
        * 100
    )

else:

    percentage = 0


st.progress(
    min(percentage / 100, 1.0)
)

st.write(
    f"**Present: {present_count} / "
    f"{total_strength} "
    f"({percentage:.2f}%)**"
)


st.divider()


# ============================================================
# SEARCH STUDENT
# ============================================================

st.subheader("🔎 Search Student")

search_text = st.text_input(
    "Search by Student Name or Student ID",
    placeholder="Example: KARANAM or 706"
)


if search_text.strip():

    with st.spinner("Searching..."):

        try:

            students = search_students(
                search_text
            )

        except Exception as e:

            students = []

            st.error(
                f"Search error: {e}"
            )


    if not students:

        st.warning(
            "❌ No student found."
        )

    else:

        st.success(
            f"✅ {len(students)} student(s) found."
        )


        # ----------------------------------------------------
        # Student selection
        # ----------------------------------------------------

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


        selected_student = (
            student_options[selected_label]
        )


        student_id = selected_student[
            "student_id"
        ]


        # ====================================================
        # STUDENT DETAILS
        # ====================================================

        st.subheader("👤 Student Details")


        detail1, detail2, detail3, detail4 = (
            st.columns(4)
        )


        with detail1:

            st.write("**Student ID**")

            st.write(
                selected_student["student_id"]
            )


        with detail2:

            st.write("**Student Name**")

            st.write(
                selected_student["student_name"]
            )


        with detail3:

            st.write("**Branch**")

            st.write(
                selected_student["branch"]
            )


        with detail4:

            st.write("**Batch**")

            st.write(
                selected_student["batch"]
            )


        st.divider()


        # ====================================================
        # CHECK TODAY'S ATTENDANCE
        # ====================================================

        try:

            existing = get_student_attendance(
                student_id
            )

        except Exception as e:

            existing = None

            st.error(
                f"Unable to check attendance: {e}"
            )


        # ====================================================
        # ATTENDANCE ALREADY MARKED
        # ====================================================

        if existing:

            status = str(
                existing.get("status", "")
            ).lower()


            if status == "present":

                st.success(
                    "🟢 Attendance already marked "
                    "**PRESENT** today."
                )

            elif status == "absent":

                st.error(
                    "🔴 Attendance already marked "
                    "**ABSENT** today."
                )

            else:

                st.info(
                    f"Current status: "
                    f"{existing.get('status')}"
                )


            st.write(
                "### ✏️ Change Attendance"
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

                        st.success(
                            "Attendance changed "
                            "to PRESENT."
                        )

                        st.rerun()

                    except Exception as e:

                        st.error(
                            f"Unable to update: {e}"
                        )


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

                        st.success(
                            "Attendance changed "
                            "to ABSENT."
                        )

                        st.rerun()

                    except Exception as e:

                        st.error(
                            f"Unable to update: {e}"
                        )


        # ====================================================
        # NEW ATTENDANCE
        # ====================================================

        else:

            st.info(
                "No attendance marked for this "
                "student today."
            )


            st.write(
                "### 📝 Mark Attendance"
            )


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

                        st.success(
                            f"Attendance marked "
                            f"PRESENT for "
                            f"{selected_student['student_name']}."
                        )

                        st.rerun()

                    except Exception as e:

                        st.error(
                            f"Unable to save attendance: {e}"
                        )


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

                        st.success(
                            f"Attendance marked "
                            f"ABSENT for "
                            f"{selected_student['student_name']}."
                        )

                        st.rerun()

                    except Exception as e:

                        st.error(
                            f"Unable to save attendance: {e}"
                        )


# ============================================================
# COMPLETE REPORT
# ============================================================

st.divider()

st.subheader(
    "📋 Today's Attendance Report"
)

st.write(
    "The complete student report is loaded only "
    "when requested."
)


if st.button(
    "📊 View Today's Complete Report",
    use_container_width=True
):

    with st.spinner(
        "Loading all students and attendance..."
    ):

        try:

            report_df = get_full_today_report()

            st.session_state.report_df = (
                report_df
            )

        except Exception as e:

            st.error(
                f"Unable to create report: {e}"
            )

            st.session_state.report_df = None


# ============================================================
# DISPLAY REPORT
# ============================================================

if st.session_state.report_df is not None:

    report_df = st.session_state.report_df


    st.success(
        f"✅ Complete report loaded: "
        f"{len(report_df)} students"
    )


    st.dataframe(
        report_df,
        use_container_width=True,
        hide_index=True
    )


    # --------------------------------------------------------
    # DOWNLOAD CSV
    # --------------------------------------------------------

    csv_data = (
        report_df
        .to_csv(index=False)
        .encode("utf-8")
    )


    st.download_button(
        label="📥 Download Today's Attendance CSV",
        data=csv_data,
        file_name=f"attendance_{today}.csv",
        mime="text/csv",
        use_container_width=True
    )
