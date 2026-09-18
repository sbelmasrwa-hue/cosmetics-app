import streamlit as st

st.set_page_config(page_title="حاسبة تركيبات التجميل", layout="centered")

st.title("🧪 حاسبة تركيبات وتكاليف مستحضرات التجميل")

# إدخال بيانات المنتج
product_name = st.text_input("اسم المنتَج (مثال: كريم مرطب للبشرة):")
batch_size = st.number_input("الحجم الإجمالي للدفعة (جرام):", min_value=1.0, value=1000.0)

st.write("---")
st.subheader("إضافة المكونات والنسب المئوية")

# تهيئة القائمة في الجلسة
if "ingredients" not in st.session_state:
    st.session_state.ingredients = []

# نموذج إدخال المكونات
with st.form("add_ingredient_form"):
    col1, col2, col3 = st.columns([3, 2, 2])
    ing_name = col1.text_input("اسم المادة الخام")
    ing_percentage = col2.number_input("النسبة (%)", min_value=0.0, max_value=100.0, step=0.1)
    ing_cost_per_kg = col3.number_input("سعر الكيلو", min_value=0.0, step=0.5)
    
    submitted = st.form_submit_button("إضافة المادة")
    if submitted and ing_name:
        st.session_state.ingredients.append({
            "name": ing_name,
            "percentage": ing_percentage,
            "cost_per_kg": ing_cost_per_kg
        })
        st.rerun()

# عرض جدول المكونات والحسابات
if st.session_state.ingredients:
    st.write("---")
    st.subheader(f"جدول التركيبة: {product_name}")
    
    total_percentage = 0
    total_cost = 0
    
    st.markdown("| المادة | النسبة (%) | الوزن المطلوب (جرام) | التكلفة |")
    st.markdown("| --- | --- | --- | --- |")
    
    for idx, ing in enumerate(st.session_state.ingredients):
        weight = (ing["percentage"] / 100) * batch_size
        cost = (weight / 1000) * ing["cost_per_kg"]
        
        total_percentage += ing["percentage"]
        total_cost += cost
        
        st.markdown(f"| {ing['name']} | {ing['percentage']}% | {weight:.2f}g | {cost:.2f} |")
    
    st.write("---")
    st.write(f"**مجموع النسب:** {total_percentage:.1f}%")
    st.write(f"**إجمالي تكلفة المواد الخام للدفعة:** {total_cost:.2f}")

    if total_percentage != 100.0:
        st.warning("⚠️ تنبيه: إجمالي النسب المئوية يجب أن يكون 100%")

    if st.button("تصفية القائمة"):
        st.session_state.ingredients = []
        st.rerun()