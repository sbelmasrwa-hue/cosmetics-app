import streamlit as st
import sqlite3
import json

st.set_page_config(page_title="حاسبة وقاعدة بيانات مستحضرات التجميل", layout="wide")

# --- إعداد قاعدة البيانات (SQLite) ---
conn = sqlite3.connect("cosmetics_recipes.db", check_same_thread=False)
cursor = conn.cursor()

# جدول حفظ الوصفات
cursor.execute("""
    CREATE TABLE IF NOT EXISTS recipes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        bottle_cost REAL,
        electricity_cost REAL,
        other_cost REAL,
        oils_data TEXT,
        total_cost REAL
    )
""")

# جدول حفظ الزيوت والمواد المضافة حديثاً
cursor.execute("""
    CREATE TABLE IF NOT EXISTS custom_materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        size REAL,
        price REAL
    )
""")
conn.commit()

# --- المواد المجهزة مسبقاً (الافتراضية) ---
DEFAULT_MATERIALS = {
    "كريم أساس (קרם בסיס)": {"size": 1000, "price": 65},
    "جل أساس (ג׳ל בסיס)": {"size": 1000, "price": 45},
    "فيتامين E نباتي (ויטמין E)": {"size": 50, "price": 35},
    "زيت الخروع (שמן קיק)": {"size": 20, "price": 15},
    "زيت اللوز الصافي (שמן שקדים 20ml)": {"size": 20, "price": 15},
    "زيت الأوبليبيخا (שמן אובליפיחה)": {"size": 10, "price": 25},
    "سينرجيا التفتيح (סינرجיה הבהרה)": {"size": 20, "price": 40},
    "زيت أرنيكا (ארניקה) - 500ml": {"size": 500, "price": 200},
    "زيت سمسم (שומשום) - 500ml": {"size": 500, "price": 80},
    "زيت بذور العنب (זרעי ענבים) - 500ml": {"size": 500, "price": 50},
    "زيت جوجوبا (חוחובה) - 500ml": {"size": 500, "price": 160},
    "زيت بذور المشمش (גלעיני משמש) - 500ml": {"size": 500, "price": 130},
    "زيت اللوز (שקדים) - 500ml": {"size": 500, "price": 45},
    "زيت إكليل الجبل (רוזמרין) - 10ml": {"size": 10, "price": 30},
    "زيت كاجبوت (קג'פוט) - 10ml": {"size": 10, "price": 30},
    "زيت زنجبيل (ג'נג'ر) - 10ml": {"size": 10, "price": 40},
    "زيت فلفل أسود (פלפל שחור) - 10ml": {"size": 10, "price": 35},
    "زيت جريب فروت (אשכולית) - 10ml": {"size": 10, "price": 25},
    "زيت أوكالبتوس (אוקליפטוס) - 10ml": {"size": 10, "price": 25},
    "زيت صنوبر (אורן) - 10ml": {"size": 10, "price": 25},
    "زيت نعناع (מנטה) - 10ml": {"size": 10, "price": 25},
    "زيت لافندر (לבנדר) - 10ml": {"size": 10, "price": 25},
    "زيت برتقال (תפוז) - 10ml": {"size": 10, "price": 25},
    "زيت يوسفي (מנדרינה) - 10ml": {"size": 10, "price": 25},
    "زيت لبان (לבונה) - 10ml": {"size": 10, "price": 55},
    "زيت جيرانيوم (גרניום) - 10ml": {"size": 10, "price": 45},
}

# جلب الزيوت المضافة من قاعدة البيانات ودمجها مع القائمة
all_materials = {"-- اختر مادة جاهزة أو أدخل يدويًا --": None}
all_materials.update(DEFAULT_MATERIALS)

cursor.execute("SELECT name, size, price FROM custom_materials")
for row in cursor.fetchall():
    all_materials[row[0]] = {"size": row[1], "price": row[2]}

st.title("🧪 حاسبة وقاعدة بيانات مستحضرات التجميل")

if "oils" not in st.session_state:
    st.session_state.oils = []

# --- ➕ القائمة الجانبية: إضافة زيت جديد للقائمة الدائمة ---
st.sidebar.header("➕ إضافة زيت جديد للقائمة الدائمة")
with st.sidebar.form("add_new_material_form"):
    new_mat_name = st.text_input("اسم الزيت / المادة الجديدة:")
    new_mat_size = st.number_input("الحجم (مل / جرام):", min_value=0.1, value=10.0)
    new_mat_price = st.number_input("سعر الشراء (₪):", min_value=0.0, value=30.0)
    
    save_mat_btn = st.form_submit_button("حفظ الزيت بالقائمة")
    if save_mat_btn and new_mat_name:
        try:
            cursor.execute("INSERT OR REPLACE INTO custom_materials (name, size, price) VALUES (?, ?, ?)", 
                           (new_mat_name, new_mat_size, new_mat_price))
            conn.commit()
            st.sidebar.success(f"تمت إضافة '{new_mat_name}' بنجاح!")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"خطأ في الحفظ: {e}")

st.sidebar.write("---")

# --- 📚 القائمة الجانبية: استرجاع الوصفات المحفوظة ---
st.sidebar.header("📚 الوصفات المحفوظة")
cursor.execute("SELECT name FROM recipes")
saved_recipes = [row[0] for row in cursor.fetchall()]
selected_recipe = st.sidebar.selectbox("اختر وصفة لاستعراضها:", ["-- جديد --"] + saved_recipes)

if selected_recipe != "-- جديد --" and st.sidebar.button("تحميل الوصفة"):
    cursor.execute("SELECT * FROM recipes WHERE name = ?", (selected_recipe,))
    recipe_data = cursor.fetchone()
    if recipe_data:
        st.session_state.load_name = recipe_data[1]
        st.session_state.load_bottle = recipe_data[2]
        st.session_state.load_elec = recipe_data[3]
        st.session_state.load_other = recipe_data[4]
        st.session_state.oils = json.loads(recipe_data[5])
        st.rerun()

# --- 1️⃣ البيانات الأساسية ---
st.header("1️⃣ بيانات المنتج والتكاليف الإضافية")
col_p1, col_p2 = st.columns(2)
product_name = col_p1.text_input("اسم المنتج / التركيبة:", value=st.session_state.get("load_name", "سيروم طبيعي"))
bottle_cost = col_p2.number_input("سعر العلبة/الزجاجة الفارغة (₪):", min_value=0.0, value=st.session_state.get("load_bottle", 2.0))

col_p3, col_p4 = st.columns(2)
electricity_overhead = col_p3.number_input("تكلفة الكهرباء والخدمات (₪):", min_value=0.0, value=st.session_state.get("load_elec", 1.0))
other_costs = col_p4.number_input("مصاريف أخرى (ملصقات، شحن) (₪):", min_value=0.0, value=st.session_state.get("load_other", 0.5))

st.write("---")

# --- 2️⃣ اختيار المكونات ---
st.header("2️⃣ إضافة الزيوت والمكونات")

selected_preset = st.selectbox("اختر مادة جاهزة من القائمة للتعبئة التلقائية:", list(all_materials.keys()))

default_name = ""
default_size = 10.0
default_price = 50.0

if selected_preset and all_materials[selected_preset]:
    default_name = selected_preset
    default_size = float(all_materials[selected_preset]["size"])
    default_price = float(all_materials[selected_preset]["price"])

with st.form("add_oil_form"):
    col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
    oil_name = col1.text_input("اسم الزيت / المادة الخام", value=default_name)
    package_size_ml = col2.number_input("حجم العبوة (مل)", min_value=0.1, value=default_size)
    package_price = col3.number_input("سعر العبوة (₪)", min_value=0.0, value=default_price)
    drops_used = col4.number_input("عدد النقاط المستخدمة", min_value=1, value=10)
    
    submitted = st.form_submit_button("إضافة الزيت للتركيبة")
    if submitted and oil_name:
        st.session_state.oils.append({
            "name": oil_name,
            "package_size": package_size_ml,
            "package_price": package_price,
            "drops": drops_used
        })
        st.rerun()

# --- 3️⃣ عرض التفاصيل والحسابات ---
total_oils_cost = 0.0
total_volume_ml = 0.0

if st.session_state.oils:
    st.write("---")
    st.subheader(f"📋 تفاصيل تركيبة: {product_name}")
    
    table_data = []
    for item in st.session_state.oils:
        cost_per_ml = item["package_price"] / item["package_size"]
        volume_ml = item["drops"] / 20.0
        cost = volume_ml * cost_per_ml
        
        total_oils_cost += cost
        total_volume_ml += volume_ml
        
        table_data.append({
            "الزيت": item["name"],
            "حجم العبوة": f"{item['package_size']} مل",
            "سعر العبوة": f"{item['package_price']:.2f} ₪",
            "عدد النقاط": f"{item['drops']} نقطة",
            "الحجم (مل)": f"{volume_ml:.2f} مل",
            "التكلفة": f"{cost:.2f} ₪"
        })
    
    st.table(table_data)

    total_product_cost = total_oils_cost + bottle_cost + electricity_overhead + other_costs

    st.write("### 💰 ملخص التكلفة وتسعير البيع")
    c1, c2, c3 = st.columns(3)
    c1.metric("تكلفة الزيوت والمواد", f"{total_oils_cost:.2f} ₪")
    c2.metric("حجم العبوة الإجمالي", f"{total_volume_ml:.2f} مل")
    c3.metric("إجمالي تكلفة العبوة الشاملة", f"{total_product_cost:.2f} ₪")

    profit_margin = st.slider("حدد نسبة الربح المطلوبة (%):", min_value=0, max_value=300, value=100, step=5)
    profit_amount = total_product_cost * (profit_margin / 100)
    final_selling_price = total_product_cost + profit_amount

    r1, r2 = st.columns(2)
    r1.success(f"**سعر البيع المقترح:** {final_selling_price:.2f} ₪")
    r2.info(f"**صافي الربح:** {profit_amount:.2f} ₪")

    col_save, col_clear = st.columns([1, 1])
    if col_save.button("💾 حفظ الوصفة في قاعدة البيانات"):
        if product_name:
            oils_json = json.dumps(st.session_state.oils)
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO recipes (name, bottle_cost, electricity_cost, other_cost, oils_data, total_cost)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (product_name, bottle_cost, electricity_overhead, other_costs, oils_json, total_product_cost))
                conn.commit()
                st.success(f"تم حفظ الوصفة '{product_name}' بنجاح!")
            except Exception as e:
                st.error(f"حدث خطأ أثناء الحفظ: {e}")
        else:
            st.warning("يرجى إدخال اسم المنتج قبل الحفظ.")

    if col_clear.button("تفريغ القائمة للبدء من جديد"):
        st.session_state.oils = []
        st.session_state.pop("load_name", None)
        st.rerun()
