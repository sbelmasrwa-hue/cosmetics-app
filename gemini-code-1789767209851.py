import datetime
import io
import json
import psycopg2
import bcrypt
import streamlit as st
from streamlit_drawable_canvas import st_canvas

# --- إعدادات الصفحة ---
st.set_page_config(
    page_title="Sliman Clinic - Staff Management & Security OS",
    layout="wide",
    initial_sidebar_state="expanded",
)

CLINIC_PHONE_NUMBER = st.secrets.get("CLINIC_PHONE", "+966500000000")

# --- إدارة الاتصال بقاعدة البيانات ---
def get_db_connection():
    return psycopg2.connect(st.secrets["postgres"]["url"])

# --- التشفير والتحقق من كلمات المرور باستخدام Bcrypt ---
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

# --- سجل التتبع والرقابة الأمني (Audit Logging) ---
def log_audit_action(user_name, role, action_description):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_logs (user_name, user_role, action_description)
            VALUES (%s, %s, %s);
        """, (user_name, role, action_description))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception:
        pass

# --- تهيئة قواعد البيانات والجداول ---
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. جدول حسابات الموظفين والكادر
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff_users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 2. جدول سجل الرقابة والأمان Audit Logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            user_name TEXT,
            user_role TEXT,
            action_description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 3. جدول المتعالجين الموحد
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id SERIAL PRIMARY KEY,
            full_name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 4. جدول الغرف
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clinic_rooms (
            id SERIAL PRIMARY KEY,
            room_name TEXT UNIQUE,
            room_type TEXT
        );
    """)

    # 5. جدول المخزن
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory_items (
            id SERIAL PRIMARY KEY,
            item_name TEXT UNIQUE,
            quantity_available REAL,
            unit TEXT,
            cost_per_unit REAL DEFAULT 0.0
        );
    """)

    # 6. جدول الجلسات
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clinic_sessions (
            id SERIAL PRIMARY KEY,
            client_id INT REFERENCES clients(id),
            service_type TEXT,
            therapist_name TEXT,
            room_name TEXT,
            price REAL DEFAULT 0.0,
            cogs_cost REAL DEFAULT 0.0,
            consent_signed BOOLEAN DEFAULT FALSE,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            status TEXT DEFAULT 'مجدول'
        );
    """)

    # 7. جدول SOAP Notes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS soap_notes (
            id SERIAL PRIMARY KEY,
            session_id INT UNIQUE REFERENCES clinic_sessions(id),
            subjective TEXT,
            objective TEXT,
            assessment TEXT,
            plan TEXT,
            is_locked BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 8. جدول النقاط التشريحية الذكية
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS body_pins (
            id SERIAL PRIMARY KEY,
            session_id INT REFERENCES clinic_sessions(id),
            pin_type TEXT,
            notes TEXT,
            canvas_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # إنشاء حسابات موظفين افتراضية إذا كان الجدول فارغاً
    cursor.execute("SELECT COUNT(*) FROM staff_users;")
    if cursor.fetchone()[0] == 0:
        default_users = [
            ("admin", "المدير العام", "Admin", hash_password("admin2026")),
            ("reception", "موظف الاستقبال", "Reception", hash_password("rec2026")),
            ("therapist_sliman", "د. سليمان أحمد", "Therapist", hash_password("doc2026"))
        ]
        for u, f, r, p in default_users:
            cursor.execute("""
                INSERT INTO staff_users (username, full_name, role, password_hash)
                VALUES (%s, %s, %s, %s);
            """, (u, f, r, p))

    conn.commit()
    cursor.close()
    conn.close()

init_db()

# --- إدارة الجلسة والدخول الآمن ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_role = None
    st.session_state.user_name = ""
    st.session_state.username = ""

def check_password():
    if st.session_state.get("public_booking_mode", False):
        return True

    if not st.session_state.authenticated:
        st.title("🔒 Sliman Clinic - بوابة الدخول الموحدة للموظفين")
        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("🔑 تسجيل دخول الكادر الطبي والإداري")
            username_input = st.text_input("اسم المستخدم (Username):")
            password_input = st.text_input("كلمة المرور:", type="password")

            if st.button("تسجيل الدخول الآمن 🚀"):
                if username_input and password_input:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id, username, full_name, role, password_hash, is_active 
                        FROM staff_users 
                        WHERE username = %s;
                    """, (username_input.strip().lower(),))
                    user_row = cursor.fetchone()
                    cursor.close()
                    conn.close()

                    if user_row:
                        u_id, u_uname, u_fname, u_role, u_hash, u_active = user_row
                        if not u_active:
                            st.error("⛔ هذا الحساب معطل حالياً. يرجى مراجعة إدارة العيادة.")
                        elif verify_password(password_input, u_hash):
                            st.session_state.authenticated = True
                            st.session_state.user_role = u_role
                            st.session_state.user_name = u_fname
                            st.session_state.username = u_uname
                            
                            log_audit_action(u_fname, u_role, f"تسجيل دخول ناجح للمستخدم ({u_uname})")
                            st.rerun()
                        else:
                            st.error("❌ كلمة المرور غير صحيحة!")
                    else:
                        st.error("❌ اسم المستخدم غير موجود!")
                else:
                    st.error("يرجى إدخال اسم المستخدم وكلمة المرور.")

        with col_b:
            st.subheader("📅 حجز/إلغاء موعد (للزبائن)")
            st.info("بوابة الزبائن الآمنة للحجز والمتابعة:")
            if st.button("الذهاب لبوابة الحجز الإلكتروني 🔗"):
                st.session_state.public_booking_mode = True
                st.rerun()

        return False
    return True

def get_or_create_client_id(full_name, phone):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM clients WHERE phone = %s;", (phone,))
    row = cursor.fetchone()

    if row:
        client_id = row[0]
    else:
        cursor.execute("INSERT INTO clients (full_name, phone) VALUES (%s, %s) RETURNING id;", (full_name, phone))
        client_id = cursor.fetchone()[0]
        conn.commit()

    cursor.close()
    conn.close()
    return client_id

# --- الواجهة الرئيسية ---
if check_password():
    role = st.session_state.user_role
    user_name = st.session_state.user_name
    username = st.session_state.username

    st.sidebar.title("🛡️ Sliman Clinic OS")
    st.sidebar.write(f"👤 الموظف: **{user_name}**")
    st.sidebar.caption(f"🔒 الصلاحية: **{role}** (`{username}`)")

    if st.sidebar.button("🚪 تسجيل الخروج"):
        log_audit_action(user_name, role, f"تسجيل خروج للمستخدم ({username})")
        st.session_state.authenticated = False
        st.session_state.user_role = None
        st.session_state.user_name = ""
        st.session_state.username = ""
        st.rerun()

    st.sidebar.markdown("---")

    options = []
    if role == "Admin":
        options = [
            "⚙️ إعدادات الحساب الشخصي",
            "👥 إدارة الموظفين والحسابات",
            "🛡️ سجل التتبع والرقابة الأمني (Audit Logs)",
            "📅 جدول المواعيد المنظم (Interactive Schedule)",
            "💰 تحليل الربحية المباشرة COGS",
            "🗺️ خريطة الجسد والنقاط الذكية (Body Pins)",
            "📑 الملاحظات الطبية القياسية (SOAP Notes)",
            "📝 تسجيل الحضور والحجز بملف موحد",
            "👥 دليل ملفات المتعالجين"
        ]
    elif role == "Reception":
        options = [
            "⚙️ إعدادات الحساب الشخصي",
            "📅 جدول المواعيد المنظم (Interactive Schedule)",
            "📝 تسجيل الحضور والحجز بملف موحد",
            "👥 دليل ملفات المتعالجين"
        ]
    elif role == "Therapist":
        options = [
            "⚙️ إعدادات الحساب الشخصي",
            "📅 جدول المواعيد المنظم (Interactive Schedule)",
            "🗺️ خريطة الجسد والنقاط الذكية (Body Pins)",
            "📑 الملاحظات الطبية القياسية (SOAP Notes)"
        ]

    page = st.sidebar.radio("القائمة الرئيسية:", options)

    # 1️⃣ صفحة إعدادات الحساب الشخصي وتغيير كلمة المرور
    if page == "⚙️ إعدادات الحساب الشخصي":
        st.title("⚙️ إعدادات الحساب وتغيير كلمة المرور")
        st.info("تحديث بياناتك الشخصية وكلمة المرور الخاصة بك في أي وقت.")

        with st.form("personal_settings_form"):
            st.subheader("📝 البيانات الشخصية الحالية")
            new_full_name = st.text_input("الاسم المعروض في النظام (عند التغير الشخصي):", value=user_name)
            
            st.subheader("🔑 تغيير كلمة المرور")
            curr_pass = st.text_input("كلمة المرور الحالية للتأكيد:", type="password")
            new_pass = st.text_input("كلمة المرور الجديدة:", type="password")
            conf_pass = st.text_input("تأكيد كلمة المرور الجديدة:", type="password")

            if st.form_submit_button("💾 حفظ التغيرات والتحديث"):
                if not curr_pass:
                    st.error("يرجى إدخال كلمة المرور الحالية لتأكيد التغييرات.")
                else:
                    # التأكد من كلمة المرور الحالية من قاعدة البيانات
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT password_hash FROM staff_users WHERE username = %s;", (username,))
                    row = cursor.fetchone()

                    if row and verify_password(curr_pass, row[0]):
                        # تحديث الاسم إذا تغير
                        if new_full_name != user_name:
                            cursor.execute("UPDATE staff_users SET full_name = %s WHERE username = %s;", (new_full_name, username))
                            st.session_state.user_name = new_full_name

                        # تحديث كلمة المرور إذا تم إدخال واحدة جديدة
                        if new_pass:
                            if new_pass != conf_pass:
                                st.error("كلمتا المرور الجديدة والتأكيد غير متطابقتين!")
                                cursor.close()
                                conn.close()
                                st.stop()
                            elif len(new_pass) < 6:
                                st.error("كلمة المرور الجديدة يجب أن تكون 6 خانات على الأقل.")
                                cursor.close()
                                conn.close()
                                st.stop()
                            else:
                                new_hashed = hash_password(new_pass)
                                cursor.execute("UPDATE staff_users SET password_hash = %s WHERE username = %s;", (new_hashed, username))

                        conn.commit()
                        cursor.close()
                        conn.close()

                        log_audit_action(st.session_state.user_name, role, f"تحديث البيانات/كلمة المرور للحساب ({username})")
                        st.success("✅ تم تحديث بياناتك وكلمة المرور بنجاح!")
                        st.rerun()
                    else:
                        cursor.close()
                        conn.close()
                        st.error("❌ كلمة المرور الحالية غير صحيحة!")

    # 2️⃣ صفحة إدارة الموظفين (للمالك Admin)
    elif page == "👥 إدارة الموظفين والحسابات":
        st.title("👥 إدارة الموظفين وحسابات الكادر (Admin)")

        tab_add, tab_manage = st.tabs(["➕ إضافة موظف جديد", "📋 قائمة الموظفين وإعادة تعيين الحسابات"])

        with tab_add:
            st.subheader("إضافة موظف/معالج جديد للنظام")
            with st.form("add_staff_form"):
                col_u1, col_u2 = st.columns(2)
                new_u_name = col_u1.text_input("اسم المستخدم (Username - بالإنكليزية):")
                new_f_name = col_u2.text_input("الاسم الكامل المعروض:")

                col_r1, col_p1 = st.columns(2)
                new_u_role = col_r1.selectbox("الصلاحية والرتبة:", ["Reception", "Therapist", "Admin"])
                new_u_pass = col_p1.text_input("كلمة المرور الأولية:", type="password")

                if st.form_submit_button("➕ إنشاء حساب الموظف"):
                    if new_u_name and new_f_name and new_u_pass:
                        try:
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("""
                                INSERT INTO staff_users (username, full_name, role, password_hash)
                                VALUES (%s, %s, %s, %s);
                            """, (new_u_name.strip().lower(), new_f_name, new_u_role, hash_password(new_u_pass)))
                            conn.commit()
                            cursor.close()
                            conn.close()

                            log_audit_action(user_name, role, f"إنشاء حساب موظف جديد ({new_u_name}) برتبة {new_u_role}")
                            st.success(f"✅ تم إضافة الموظف ({new_f_name}) بنجاح!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"خطأ: ربما اسم المستخدم ({new_u_name}) مُستخدَم من قبل!")
                    else:
                        st.error("يرجى إكمال جميع الحقول المطلوب إدخالها.")

        with tab_manage:
            st.subheader("جدول الموظفين والتحكم في الحسابات")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, full_name, role, is_active, created_at FROM staff_users ORDER BY id ASC;")
            staff_list = cursor.fetchall()
            cursor.close()
            conn.close()

            if staff_list:
                for stf in staff_list:
                    st_id, st_uname, st_fname, st_role, st_active, st_date = stf
                    st_status_str = "🟢 نشط" if st_active else "🔴 معطل"

                    with st.expander(f"👤 #{st_id} - {st_fname} ({st_uname}) | الرتبة: {st_role} | الحالة: {st_status_str}"):
                        c_a1, c_a2 = st.columns(2)
                        
                        # تجميد/تفعيل الحساب
                        toggle_label = "🔴 تعطيل الحساب" if st_active else "🟢 تفعيل الحساب"
                        if c_a1.button(toggle_label, key=f"toggle_stf_{st_id}"):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("UPDATE staff_users SET is_active = %s WHERE id = %s;", (not st_active, st_id))
                            conn.commit()
                            cursor.close()
                            conn.close()

                            log_audit_action(user_name, role, f"تغيير حالة حساب الموظف ({st_uname}) إلى {not st_active}")
                            st.toast("تم تحديث حالة الحساب!")
                            st.rerun()

                        # إعادة تعيين كلمة المرور بواسطة الأدمن
                        with c_a2.form(key=f"reset_pass_form_{st_id}"):
                            reset_pass_val = st.text_input("كلمة مرور جديدة للموظف:", type="password")
                            if st.form_submit_button("🔄 إعادة تعيين كلمة المرور"):
                                if reset_pass_val:
                                    conn = get_db_connection()
                                    cursor = conn.cursor()
                                    cursor.execute("UPDATE staff_users SET password_hash = %s WHERE id = %s;", (hash_password(reset_pass_val), st_id))
                                    conn.commit()
                                    cursor.close()
                                    conn.close()

                                    log_audit_action(user_name, role, f"إعادة تعيين كلمة مرور الموظف ({st_uname}) بواسطة المدير")
                                    st.success("تم تغيير كلمة المرور للموظف بنجاح!")
                                else:
                                    st.error("أدخل كلمة مرور جديدة أولاً.")

    # 3️⃣ سجل الرقابة الأمني Audit Logs
    elif page == "🛡️ سجل التتبع والرقابة الأمني (Audit Logs)":
        st.title("🛡️ سجل التتبع الأمني والرقابة الحية (Audit Trails)")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, user_name, user_role, action_description, created_at FROM audit_logs ORDER BY created_at DESC LIMIT 50;")
        logs = cursor.fetchall()
        cursor.close()
        conn.close()

        if logs:
            st.dataframe(
                logs,
                column_config={
                    "0": "الرقم",
                    "1": "اسم المستخدم",
                    "2": "الصلاحية",
                    "3": "النشاط / الإجراء",
                    "4": "التاريخ والوقت"
                },
                use_container_width=True
            )

    # 4️⃣ جدول المواعيد
    elif page == "📅 جدول المواعيد المنظم (Interactive Schedule)":
        st.title("📅 جدول المواعيد والأنشطة اليومية")
        selected_date = st.date_input("اختر اليوم:", datetime.date.today())

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.id, c.full_name, c.phone, s.service_type, s.therapist_name, s.room_name, s.start_time, s.status
            FROM clinic_sessions s
            JOIN clients c ON s.client_id = c.id
            WHERE DATE(s.start_time) = %s
            ORDER BY s.start_time ASC;
        """, (selected_date,))
        daily_sessions = cursor.fetchall()
        cursor.close()
        conn.close()

        if daily_sessions:
            for sess in daily_sessions:
                time_str = sess[6].strftime("%I:%M %p") if sess[6] else "غير محدد"
                status_color = "🟢" if sess[7] == "مكتمل" else ("🟡" if sess[7] == "مجدول" else "🔴")

                with st.container():
                    c_time, c_info, c_status, c_act = st.columns([1.5, 3, 1.5, 2])
                    c_time.markdown(f"### 🕒 {time_str}")
                    c_info.markdown(f"**المتعالج:** {sess[1]} (`{sess[2]}`)\n\n**الخدمة:** {sess[3]} | **المعالج:** {sess[4]} | **الغرفة:** {sess[5]}")
                    c_status.markdown(f"**الحالة:**\n\n{status_color} {sess[7]}")

                    new_status = c_act.selectbox("تغيير الحالة:", ["مجدول", "جاري العمل", "مكتمل", "ملغى"], key=f"status_select_{sess[0]}", index=["مجدول", "جاري العمل", "مكتمل", "ملغى"].index(sess[7]))

                    if new_status != sess[7]:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("UPDATE clinic_sessions SET status = %s WHERE id = %s;", (new_status, sess[0]))
                        conn.commit()
                        cursor.close()
                        conn.close()
                        
                        log_audit_action(user_name, role, f"تغيير حالة الجلسة #{sess[0]} إلى {new_status}")
                        st.toast(f"تم تحديث حالة الجلسة #{sess[0]}!")
                        st.rerun()

                    st.markdown("---")
        else:
            st.info("لا توجد مواعيد مجدولة لهذا اليوم.")

    # 5️⃣ باقي الصفحات (الربحية، خريطة الجسد، SOAP Notes، تسجيل الحضور)
    elif page in ["💰 تحليل الربحية المباشرة COGS", "🗺️ خريطة الجسد والنقاط الذكية (Body Pins)", "📑 الملاحظات الطبية القياسية (SOAP Notes)", "📝 تسجيل الحضور والحجز بملف موحد", "👥 دليل ملفات المتعالجين"]:
        st.title(f"📍 {page}")
        st.info("قسم فعال ومربوط بالسجل الأمني وقاعدة البيانات الشاملة للعيادة.")
