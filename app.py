import datetime
import html
import os
import re
from io import BytesIO
import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
from PIL import Image
from supabase import create_client, Client

# --- 0. CẤU HÌNH HỆ THỐNG & BẢO MẬT ĐĂNG NHẬP ---
st.set_page_config(
    page_title="AI Video Viral",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

ADMIN_PASSWORD = "123"
MODEL_NAME = "gemini-3.8-flash"


def check_password():
    def password_entered():
        if st.session_state["password"] == ADMIN_PASSWORD:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown(
            "<h2 style='text-align: center; color: #4F46E5;'>🔒 Đăng Nhập Hệ Thống AI Video Viral</h2>",
            unsafe_allow_html=True,
        )
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.text_input(
                "Vui lòng nhập mật khẩu để truy cập App",
                type="password",
                on_change=password_entered,
                key="password",
            )
            st.warning("⚠️ App được bảo mật tuyệt đối.")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input(
            "Vui lòng nhập mật khẩu để truy cập App",
            type="password",
            on_change=password_entered,
            key="password",
        )
        st.error("❌ Mật khẩu không chính xác. Vui lòng thử lại.")
        return False
    else:
        return True


if not check_password():
    st.stop()


# --- 1. CẤU HÌNH KẾT NỐI SUPABASE DATABASE ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def configure_genai():
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    else:
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))


def save_project_db(project_name, product_info, scripts, status="Đã tạo kịch bản"):
    try:
        created_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        existing = (
            supabase.table("projects")
            .select("id")
            .eq("project_name", project_name)
            .execute()
        )

        if existing.data:
            supabase.table("projects").update({
                "product_info": product_info,
                "scripts": scripts,
                "status": status,
                "created_date": created_date,
                "is_deleted": 0,
            }).eq("project_name", project_name).execute()
        else:
            supabase.table("projects").insert({
                "project_name": project_name,
                "created_date": created_date,
                "product_info": product_info,
                "scripts": scripts,
                "status": status,
                "is_deleted": 0,
            }).execute()
    except Exception:
        pass


def get_all_projects():
    try:
        response = (
            supabase.table("projects")
            .select("id, project_name, created_date, product_info, scripts, status, is_deleted")
            .order("id", desc=True)
            .execute()
        )
        rows = []
        for item in response.data:
            if item.get("is_deleted", 0) in (0, None, False):
                rows.append((
                    item["id"],
                    item["project_name"],
                    item.get("created_date", ""),
                    item.get("product_info", ""),
                    item.get("scripts", ""),
                    item.get("status", ""),
                ))
        return rows
    except Exception:
        return []


def soft_delete_project(project_id):
    try:
        supabase.table("projects").update({"is_deleted": 1}).eq("id", project_id).execute()
    except Exception:
        pass


# --- 2. HÀM NÉN ẢNH, DỌN KÝ TỰ RÁC & NÚT COPY 1 CHẠM ---
def compress_image_for_ai(image_file, max_size=1024, quality=80):
    img = Image.open(image_file)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=quality, optimize=True)
    buffer.seek(0)
    return Image.open(buffer)


def clean_script_text(raw_text):
    if not raw_text:
        return ""
    cleaned = re.sub(r"^[\d\-\s_A-Z]+---", "", raw_text.strip())
    cleaned = cleaned.lstrip("0123456789- \n\r")
    return cleaned.strip()


def render_copy_button(text_to_copy: str, button_label: str, btn_id: str):
    escaped_text = html.escape(text_to_copy or "")
    html_code = f"""
    <div style="margin-top: 2px; margin-bottom: 10px;">
        <textarea id="ta_{btn_id}" style="position: absolute; left: -9999px; opacity: 0;">{escaped_text}</textarea>
        <button id="btn_{btn_id}" onclick="copyPrompt_{btn_id}()" style="
            width: 100%;
            background-color: #16A34A;
            color: #FFFFFF;
            border: none;
            padding: 10px 16px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            transition: background-color 0.2s ease;
        ">📋 {button_label}</button>
    </div>
    <script>
    function copyPrompt_{btn_id}() {{
        var copyText = document.getElementById("ta_{btn_id}").value;
        var btn = document.getElementById("btn_{btn_id}");
        if (navigator.clipboard && window.isSecureContext) {{
            navigator.clipboard.writeText(copyText).then(function() {{
                btn.innerHTML = "✅ Đã sao chép: {button_label}";
                btn.style.backgroundColor = "#059669";
                setTimeout(function() {{
                    btn.innerHTML = "📋 {button_label}";
                    btn.style.backgroundColor = "#16A34A";
                }}, 2000);
            }});
        }} else {{
            var textArea = document.getElementById("ta_{btn_id}");
            textArea.style.position = "fixed";
            textArea.style.opacity = "1";
            textArea.select();
            document.execCommand("copy");
            textArea.style.position = "absolute";
            textArea.style.opacity = "0";
            btn.innerHTML = "✅ Đã sao chép: {button_label}";
            btn.style.backgroundColor = "#059669";
            setTimeout(function() {{
                btn.innerHTML = "📋 {button_label}";
                btn.style.backgroundColor = "#16A34A";
            }}, 2000);
        }}
    }}
    </script>
    """
    components.html(html_code, height=52)


def parse_full_response(full_text, fallback_info=""):
    col1, col2, s1, s2, s3 = "", "", "", "", ""
    try:
        if "---SPLIT_COL1_END---" in full_text:
            c1_split = full_text.split("---SPLIT_COL1_END---")
            col1 = c1_split[0].split("---SPLIT_COL1_START---")[-1].strip()
            rest = c1_split[1]
        else:
            col1 = fallback_info
            rest = full_text

        if "---SPLIT_SCENE_" in rest:
            c2_split = rest.split("---SPLIT_SCENE_")
            col2 = (
                c2_split[0]
                .replace("---SPLIT_COL2_START---", "")
                .replace("---SPLIT_COL2_END---", "")
                .strip()
            )
            s1 = clean_script_text(c2_split[1]) if len(c2_split) > 1 else ""
            s2 = clean_script_text(c2_split[2]) if len(c2_split) > 2 else ""
            s3 = clean_script_text(c2_split[3]) if len(c2_split) > 3 else ""
        else:
            col2 = ""
            s1 = clean_script_text(rest)
    except Exception:
        col1 = fallback_info or full_text
        s1 = clean_script_text(full_text)
    return col1, col2, s1, s2, s3


# --- 3. KHỞI TẠO BIẾN SESSION STATE ---
if "current_project_name" not in st.session_state:
    st.session_state.current_project_name = f"Dự án mới - {datetime.datetime.now().strftime('%d/%m/%Y')}"
if "analysis_col1" not in st.session_state:
    st.session_state.analysis_col1 = None
if "analysis_col2" not in st.session_state:
    st.session_state.analysis_col2 = None
if "script_1" not in st.session_state:
    st.session_state.script_1 = None
if "script_2" not in st.session_state:
    st.session_state.script_2 = None
if "script_3" not in st.session_state:
    st.session_state.script_3 = None
if "prompts_s1" not in st.session_state:
    st.session_state.prompts_s1 = None
if "prompts_s2" not in st.session_state:
    st.session_state.prompts_s2 = None
if "prompts_s3" not in st.session_state:
    st.session_state.prompts_s3 = None

# --- 4. THANH ĐIỀU HƯỚNG (SIDEBAR) & LỊCH SỬ DỰ ÁN ---
st.sidebar.markdown("<h3 style='text-align: center;'>🗂️ Quản lý Dự án</h3>", unsafe_allow_html=True)

if st.sidebar.button("➕ Tạo Dự Án Mới", type="primary", use_container_width=True):
    st.session_state.current_project_name = f"Dự án mới - {datetime.datetime.now().strftime('%d/%m/%Y')}"
    st.session_state.analysis_col1 = None
    st.session_state.analysis_col2 = None
    st.session_state.script_1 = None
    st.session_state.script_2 = None
    st.session_state.script_3 = None
    st.session_state.prompts_s1 = None
    st.session_state.prompts_s2 = None
    st.session_state.prompts_s3 = None
    st.rerun()

st.sidebar.divider()

st.sidebar.markdown("🏷️ **Tên Dự Án Hiện Tại**")
project_title_input = st.sidebar.text_input(
    "Tên dự án",
    value=st.session_state.current_project_name,
    label_visibility="collapsed",
)
st.session_state.current_project_name = project_title_input

st.sidebar.divider()

search_query = st.sidebar.text_input("🔍 Tìm kiếm dự án cũ", "")
projects = get_all_projects()

st.sidebar.markdown("📜 **Lịch sử dự án đã lưu**")
if not projects:
    st.sidebar.info("Chưa có dự án nào trong Database.")
else:
    for pid, pname, pdate, pinfo, pscript, pstatus in projects:
        if search_query.lower() in pname.lower():
            col_p1, col_p2 = st.sidebar.columns([4, 1])
            display_name = pname if len(pname) <= 22 else pname[:22] + "..."
            if col_p1.button(f"📁 {display_name}", key=f"load_{pid}", use_container_width=True):
                st.session_state.current_project_name = pname
                c1, c2, s1, s2, s3 = parse_full_response(pscript, pinfo)
                st.session_state.analysis_col1 = c1
                st.session_state.analysis_col2 = c2
                st.session_state.script_1 = s1
                st.session_state.script_2 = s2
                st.session_state.script_3 = s3
                st.session_state.prompts_s1 = None
                st.session_state.prompts_s2 = None
                st.session_state.prompts_s3 = None
                st.rerun()
            if col_p2.button("❌", key=f"del_{pid}"):
                soft_delete_project(pid)
                st.rerun()

st.sidebar.markdown("<br><br>", unsafe_allow_html=True)
st.sidebar.divider()
if st.sidebar.button("🚪 Đăng xuất", use_container_width=True):
    st.session_state["password_correct"] = False
    st.rerun()

# --- 5. GIAO DIỆN CHÍNH ---
st.markdown("<h1 style='text-align: center; color: #1F2937;'>🎬 AI Video Viral</h1>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align: center; color: #4B5563; font-size: 16px;'>"
    "Hệ thống tự động hóa 100% đa ngành hàng: Chỉ trích xuất sản phẩm & biến thể Hot 🔥/Lượt bán từ ảnh gốc, "
    "còn nhân vật & bối cảnh được AI tự sáng tạo thông minh hoàn toàn mới khớp theo kịch bản thoại."
    "</p>",
    unsafe_allow_html=True,
)
st.divider()

if not st.session_state.analysis_col1:
    st.markdown("### 📦 Thông Tin Đầu Vào Sản Phẩm")
    product_images = st.file_uploader(
        "Tải lên ảnh chụp màn hình sản phẩm (có lượt bán, icon Hot 🔥, phân loại, thông số kỹ thuật, hướng dẫn sử dụng...)",
        type=["jpg", "png", "jpeg"],
        accept_multiple_files=True,
        help="Chọn nhiều ảnh để AI quét chính xác lượt bán, biến thể Hot và hiểu rõ sản phẩm.",
    )

    if product_images:
        with st.expander(f"👁️ Xem lại danh sách ảnh đã tải lên ({len(product_images)} ảnh)"):
            cols = st.columns(min(len(product_images), 3))
            for idx, img_file in enumerate(product_images):
                with cols[idx % len(cols)]:
                    st.image(img_file, caption=f"Ảnh {idx + 1}", use_container_width=True)

    user_notes = st.text_area(
        "📝 Ghi chú / Yêu cầu riêng cho kịch bản (Quyền ưu tiên cao nhất)",
        placeholder="Nhập yêu cầu riêng nếu muốn chỉ định biến thể hoặc nhấn mạnh tính năng đặc biệt...",
    )

    st.markdown("<br>", unsafe_allow_html=True)
    col_b1, col_b2, col_b3 = st.columns([1, 2, 1])
    with col_b2:
        analyze_btn = st.button(
            "🚀 Phân Tích Sản Phẩm & Tạo Kịch Bản Sáng Tạo",
            type="primary",
            use_container_width=True,
        )

    if analyze_btn:
        if not product_images:
            st.error("⚠️ Vui lòng tải lên ít nhất một ảnh sản phẩm!")
        else:
            with st.spinner("🤖 AI (gemini-3.8-flash) đang quét sản phẩm, biến thể Hot 🔥, phân tích cơ chế và viết kịch bản..."):
                try:
                    configure_genai()
                    model = genai.GenerativeModel(MODEL_NAME)
                    contents = [compress_image_for_ai(img) for img in product_images]

                    notes_instruction = (
                        f"\n🚨 GHI CHÚ ƯU TIÊN CAO NHẤT TỪ NGƯỜI DÙNG: '{user_notes}'."
                        if user_notes.strip()
                        else ""
                    )

                    prompt_text = f"""
Bạn là Giám đốc Sản xuất Video Quảng cáo AI chuyên nghiệp cho video ngắn dựng sẵn (Reels, TikTok - KHÔNG LIVESTREAM), am hiểu 100% các ngành hàng.
Hãy phân tích các hình ảnh sản phẩm được tải lên.
{notes_instruction}

1. QUY TẮC BẮT BUỘC VỀ SẢN PHẨM & BIẾN THỂ BÁN CHẠY NHẤT (HERO VARIANT):
- **Chỉ lấy sản phẩm từ ảnh:** Đọc kỹ thông tin sản phẩm, chất liệu, tính năng trên ảnh. 
- **Quét lượt bán & Biến thể Hot:** Tìm con số lượt bán (ví dụ: "Đã bán 1.2k") hoặc icon ngọn lửa 🔥 / chữ "Hot". Biến thể nào có doanh số cao nhất hoặc gắn nhãn Hot phải được chọn làm sản phẩm chủ lực (Hero Variant).
- **Tuyệt đối KHÔNG lấy nhân vật hay bối cảnh cũ từ ảnh chụp màn hình gốc:** Nhân vật KOC và bối cảnh trong các phân cảnh phía dưới phải được bạn **tự động sáng tạo mới hoàn toàn**, hiện đại, chuyên nghiệp, phù hợp với hành vi người mua và khớp hoàn toàn với câu thoại của từng cảnh.

2. CƠ CHẾ VẬT LÝ & HOẠT ĐỘNG SẢN PHẨM (PHYSICS & FUNCTIONAL LOCK):
- Mô tả chính xác thao tác nhân vật tương tác hoặc vận hành sản phẩm đúng thực tế vật lý ngoài đời (cách cầm, cách bấm nút, cách kéo khóa, độ co giãn...). Không bịa đặt chức năng sai lệch.

3. QUY TẮC 3 KHÔNG VỀ HÌNH ẢNH & ÂM THANH:
- CẤM dùng từ ngữ livestream ("mọi người ơi", "giỏ hàng phiên live", "vào phiên live").
- CẤM hiển thị 3 câu hook riêng lẻ.
- **TUYỆT ĐỐI KHÔNG TEXT (NO TEXT OVERLAY), KHÔNG LOGO, KHÔNG NHẠC NỀN (NO BACKGROUND MUSIC)** trong toàn bộ mô tả phân cảnh, ảnh và video. Chỉ có giọng nói trực tiếp của nhân vật và âm thanh hiệu ứng thực tế (SFX).

4. QUY TRÌNH SÁNG TẠO KỊCH BẢN CHUẨN XÁC:
- **Bước 1:** Viết **Kịch bản Lời thoại Voiceover Tổng thể** liền mạch (giọng Hà Nội tự nhiên).
- **Bước 2:** Chia thành các **PHÂN CẢNH 8 GIÂY**, mỗi phân cảnh **chỉ chứa từ 32 đến 40 chữ**.
- **Linh hoạt số lượng phân cảnh:** Nếu dài, tự động chia thành 4, 5 hoặc 6 phân cảnh.
- **Cấu trúc mỗi phân cảnh:** Dòng trên là `*Hình ảnh:*` (mô tả nhân vật tự sáng tạo, bối cảnh tự sáng tạo khớp ý nghĩa câu thoại, thao tác chuẩn sản phẩm), dòng dưới là `*Lời thoại phân cảnh:*` (32-40 chữ).

Dòng đầu tiên của câu trả lời PHẢI ghi chính xác: Tên sản phẩm: [Tên ngắn gọn của sản phẩm]

TRẢ VỀ KẾT QUẢ ĐÚNG THEO CÁC THẺ PHÂN TÁCH SAU:
---SPLIT_COL1_START---
### 📌 Cột Trái: Sản Phẩm Chủ Lực, Lượt Bán & Chân Dung Khách Hàng
- **1. Dữ liệu Lượt bán & Chân dung Khách hàng:**
  - *Sản phẩm & Lượt bán quét được:* [Tên sản phẩm và tổng lượt bán/đánh giá]
  - *Nỗi đau khách hàng:* [Mô tả chi tiết]
- **2. Biến Thể Chủ Lực (Hero Variant Hot 🔥):**
  - *Biến thể chọn làm trọng tâm:* [Tên/màu biến thể bán chạy nhất]
  - *Đặc tính kỹ thuật sản phẩm:* [Chất liệu, điểm nổi bật]
---SPLIT_COL1_END---

---SPLIT_COL2_START---
### 🎨 Cột Phải: Giải Phẫu Cấu Tạo & Cơ Chế Hoạt Động
- **3. Giải phẫu Cấu tạo & Cơ chế Vật lý:**
  - *Cấu tạo 3D & Kích thước:* [Thông tin chuẩn]
  - *Thao tác vận hành thực tế:* [Cách sử dụng sản phẩm đúng cơ chế]
- **4. Thông Tin Giá & Ưu Đãi:**
  - *Mức giá hiển thị:* [Giá gốc và giá sale]
---SPLIT_COL2_END---

---SPLIT_SCENE_1---
### 🎬 Kịch bản 1: Góc Review Thực Tế & Trình Diễn Tính Năng
- **Kịch bản Lời thoại Voiceover Tổng thể (Giọng Hà Nội chuẩn):** "[Viết toàn bộ lời thoại liền mạch]"
- **Phân cảnh 1 (8 giây):**
  - *Hình ảnh:* [AI tự sáng tạo nhân vật KOC hiện đại, bối cảnh khớp hoàn toàn với câu thoại cảnh này, thao tác chuẩn sản phẩm, KHÔNG TEXT, KHÔNG LOGO]
  - *Lời thoại phân cảnh (32-40 chữ):* "[Câu thoại cảnh 1]"
- **Phân cảnh 2 (8 giây):**
  - *Hình ảnh:* [AI tự sáng tạo nhân vật & bối cảnh khớp câu thoại, KHÔNG TEXT, KHÔNG LOGO]
  - *Lời thoại phân cảnh (32-40 chữ):* "[Câu thoại cảnh 2]"
(Tiếp tục Phân cảnh 3, 4...)

---SPLIT_SCENE_2---
### 🎬 Kịch bản 2: Góc Giải Quyết Nỗi Đau & Tình Huống Thực Tế
- **Kịch bản Lời thoại Voiceover Tổng thể (Giọng Hà Nội chuẩn):** "[Viết toàn bộ lời thoại liền mạch]"
- **Phân cảnh 1 (8 giây):**
  - *Hình ảnh:* [AI tự sáng tạo nhân vật & bối cảnh khớp câu thoại, KHÔNG TEXT, KHÔNG LOGO]
  - *Lời thoại phân cảnh (32-40 chữ):* "[Câu thoại cảnh 1]"
(Tiếp tục Phân cảnh 2, 3...)

---SPLIT_SCENE_3---
### 🎬 Kịch bản 3: Góc Kiểm Chứng Chất Lượng & Ưu Đãi Sốc
- **Kịch bản Lời thoại Voiceover Tổng thể (Giọng Hà Nội chuẩn):** "[Viết toàn bộ lời thoại liền mạch]"
- **Phân cảnh 1 (8 giây):**
  - *Hình ảnh:* [AI tự sáng tạo nhân vật & bối cảnh khớp câu thoại, KHÔNG TEXT, KHÔNG LOGO]
  - *Lời thoại phân cảnh (32-40 chữ):* "[Câu thoại cảnh 1]"
(Tiếp tục Phân cảnh 2, 3...)
"""
                    contents.append(prompt_text)

                    response = model.generate_content(contents)
                    full_text = response.text

                    c1, c2, s1, s2, s3 = parse_full_response(full_text)
                    st.session_state.analysis_col1 = c1
                    st.session_state.analysis_col2 = c2
                    st.session_state.script_1 = s1
                    st.session_state.script_2 = s2
                    st.session_state.script_3 = s3
                    st.session_state.prompts_s1 = None
                    st.session_state.prompts_s2 = None
                    st.session_state.prompts_s3 = None

                    extracted_name = "Dự án sản phẩm"
                    for line in full_text.split("\n"):
                        if "tên sản phẩm" in line.lower():
                            extracted_name = line.split(":", 1)[-1].replace("*", "").replace("#", "").strip()
                            break
                    if len(extracted_name) > 35:
                        extracted_name = extracted_name[:35] + "..."

                    st.session_state.current_project_name = (
                        f"{extracted_name} - {datetime.datetime.now().strftime('%d/%m/%Y')}"
                    )

                    save_project_db(
                        st.session_state.current_project_name,
                        st.session_state.analysis_col1 + "\n\n" + st.session_state.analysis_col2,
                        full_text,
                    )
                    st.success("✅ Phân tích thành công, đã lưu lên Supabase!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi khi gọi API: {e}")

# --- 6. HIỂN THỊ GIAO DIỆN 2 CỘT ĐỐI XỨNG & XUẤT PROMPT KÈM NÚT COPY 1 CHẠM ---
if st.session_state.analysis_col1:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        "<h2 style='text-align: center; color: #4F46E5;'>🔍 Phân Tích Sản Phẩm, Biến Thể Hot & Cơ Chế Hoạt Động</h2>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown(st.session_state.analysis_col1)
    with col_right:
        st.markdown(st.session_state.analysis_col2 if st.session_state.analysis_col2 else "Đang cập nhật...")

    st.markdown("<br><hr><br>", unsafe_allow_html=True)
    st.markdown(
        "<h2 style='text-align: center; color: #4F46E5;'>🎬 Kịch Bản Quảng Cáo & Xuất Prompt Sáng Tạo Ảnh / Video Veo 3</h2>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    def handle_script_section(script_title, script_content, state_key):
        if not script_content:
            return
        st.markdown(script_content)

        if st.button(
            f"👉 Xuất Bộ Prompt Ảnh & Video Veo 3 cho {script_title} (Nhân Vật & Bối Cảnh Tự Sáng Tạo Khớp Thoại)",
            key=f"btn_{state_key}",
            type="primary",
            use_container_width=True,
        ):
            with st.spinner(f"🤖 Đang tạo bộ Prompt Ảnh & Video Veo 3 (Sáng tạo nhân vật & bối cảnh linh hoạt theo câu thoại) cho {script_title}..."):
                try:
                    configure_genai()
                    model = genai.GenerativeModel(MODEL_NAME)

                    master_context = f"{st.session_state.analysis_col1}\n{st.session_state.analysis_col2}"
                    prompt_gen = f"""
Dựa vào THÔNG TIN SẢN PHẨM CHỦ LỰC VÀ BIẾN THỂ HOT dưới đây:
{master_context}

Và nội dung chi tiết của từng phân cảnh trong {script_title} dưới đây:
{script_content}

Hãy xuất bộ Prompt tạo Ảnh tĩnh (Midjourney/Flux) và Prompt tạo Video (Veo 3 Pro) cho TẤT CẢ CÁC PHÂN CẢNH có trong kịch bản trên.

YÊU CẦU NGHIÊM NGẶT VỀ NHÂN VẬT & BỐI CẢNH SÁNG TẠO:
1. **CHỈ LẤY SẢN PHẨM LÀM TRỌNG TÂM:** Không sao chép nhân vật hay bối cảnh cũ từ ảnh chụp màn hình gốc. Hãy **tự do sáng tạo nhân vật KOC hiện đại, chuyên nghiệp và thiết kế bối cảnh không gian hoàn toàn mới, sống động, khớp tuyệt đối 100% với ý nghĩa câu thoại** của từng phân cảnh.
2. **ĐÚNG CƠ CHẾ VẬT LÝ & CHỨC NĂNG SẢN PHẨM:** Mô tả chính xác thao tác nhân vật tương tác vận hành sản phẩm đúng thực tế vật lý.
3. **TUYỆT ĐỐI KHÔNG TEXT, KHÔNG LOGO, KHÔNG NHẠC NỀN:** Gắn cụm `no text, no words, no watermark, no logo` ở prompt ảnh, và `no background music, no text overlay, no logo, studio quality audio` ở prompt video.
4. **NHÂN VẬT TRỰC TIẾP THOẠI TRONG VIDEO (VEO 3 LIP-SYNC DIALOGUE):** Trong `VID_PROMPT`, bắt buộc có chỉ dẫn nhân vật nói trực tiếp câu thoại tiếng Việt của phân cảnh đó với giọng nữ Hà Nội tự nhiên, khớp khẩu hình miệng (Ví dụ: `The Vietnamese female KOC speaks naturally in a clear Hanoi accent with accurate lip-sync, saying: "[Chèn nguyên văn câu thoại tiếng Việt của phân cảnh đó]"`), đi kèm âm thanh thực tế của sản phẩm (realistic product SFX).

BẮT BUỘC TRẢ VỀ ĐÚNG ĐỊNH DẠNG SAU CHO TỪNG PHÂN CẢNH:
===SCENE_SPLIT===
SCENE_NUM: [Số thứ tự cảnh, ví dụ: 1]
IMG_PROMPT: [DYNAMIC SETTING & CHARACTER]: Vertical 9:16 photorealistic medium shot, [Mô tả nhân vật KOC do AI tự sáng tạo + BỐI CẢNH MỚI KHỚP TUYỆT ĐỐI VỚI NỘI DUNG THOẠI + sản phẩm biến thể Hot + hành động tương tác đúng chức năng], 8k resolution, photorealistic, no text, no logo --ar 9:16
VID_PROMPT: [PRODUCT-CENTRIC CAMERA & DYNAMIC SCENE]: Vertical 9:16 stable cinematic shot, [Mô tả nhân vật KOC + Bối cảnh mới khớp thoại + chuyển động sử dụng/trình diễn sản phẩm đúng cơ chế vật lý mượt mà]. The character speaks directly with natural facial expressions and accurate lip-sync in a clear Vietnamese Hanoi female voice, saying: "[Nguyên văn câu lời thoại tiếng Việt của phân cảnh này]". Studio quality voice audio, realistic product interaction sound effects, no background music, no text, no logo, anti-stutter.
"""
                    res = model.generate_content(prompt_gen)
                    st.session_state[state_key] = res.text
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi khi tạo Prompt: {e}")

        p_text = st.session_state.get(state_key)
        if p_text:
            st.markdown("<br>", unsafe_allow_html=True)
            scenes = p_text.split("===SCENE_SPLIT===")
            scene_idx = 0
            for sc in scenes:
                if not sc.strip():
                    continue
                scene_idx += 1
                s_num = str(scene_idx)
                img_p = ""
                vid_p = ""

                for line in sc.strip().split("\n"):
                    line_clean = line.strip()
                    if line_clean.startswith("SCENE_NUM:"):
                        s_num = line_clean.replace("SCENE_NUM:", "").strip()
                    elif line_clean.startswith("IMG_PROMPT:"):
                        img_p = line_clean.replace("IMG_PROMPT:", "").strip()
                    elif line_clean.startswith("VID_PROMPT:"):
                        vid_p = line_clean.replace("VID_PROMPT:", "").strip()

                final_img_p = img_p if img_p else sc.strip()
                final_vid_p = vid_p if vid_p else sc.strip()

                p_col1, p_col2 = st.columns(2)
                with p_col1:
                    st.markdown(f"🖼️ **Prompt Ảnh Tinh Gọn Cảnh {s_num} (Midjourney / Flux):**")
                    st.code(final_img_p, language="text")
                    render_copy_button(
                        final_img_p,
                        f"Sao Chép Prompt Ảnh Cảnh {s_num}",
                        f"img_{state_key}_{scene_idx}",
                    )
                with p_col2:
                    st.markdown(f"🎥 **Prompt Video Tinh Gọn Cảnh {s_num} (Veo 3 Pro - Âm thanh Studio, Chống Vấp Thoại):**")
                    st.code(final_vid_p, language="text")
                    render_copy_button(
                        final_vid_p,
                        f"Sao Chép Prompt Video Cảnh {s_num}",
                        f"vid_{state_key}_{scene_idx}",
                    )

                st.markdown("<br>", unsafe_allow_html=True)

    # --- HIỂN THỊ 3 KỊCH BẢN ---
    handle_script_section("Kịch bản 1", st.session_state.script_1, "prompts_s1")
    st.markdown("<br><hr><br>", unsafe_allow_html=True)

    handle_script_section("Kịch bản 2", st.session_state.script_2, "prompts_s2")
    st.markdown("<br><hr><br>", unsafe_allow_html=True)

    handle_script_section("Kịch bản 3", st.session_state.script_3, "prompts_s3")

    st.markdown("<br><hr><br>", unsafe_allow_html=True)

    # --- TẠO THÊM KỊCH BẢN MỚI ---
    st.markdown("#### ➕ Tạo Thêm Kịch Bản Mới (Góc Tiếp Cận Khác)")
    extra_user_notes = st.text_area(
        "📝 Ghi chú / Yêu cầu riêng cho lần gọi thêm này (Tùy chọn)",
        placeholder="Nhập yêu cầu riêng cho các kịch bản gọi thêm...",
        key="extra_notes_input",
    )

    if st.button("🚀 Gọi thêm 3 Kịch bản mới theo yêu cầu", type="primary", use_container_width=True):
        with st.spinner("🤖 AI đang sáng tạo thêm 3 kịch bản mới bám sát sản phẩm & tự do sáng tạo bối cảnh linh hoạt..."):
            try:
                configure_genai()
                model = genai.GenerativeModel(MODEL_NAME)
                extra_note_instruction = (
                    f"\n🚨 GHI CHÚ RIÊNG: '{extra_user_notes}'."
                    if extra_user_notes.strip()
                    else ""
                )
                master_context = f"{st.session_state.analysis_col1}\n{st.session_state.analysis_col2}"
                extra_prompt = f"""
Dựa trên BẢNG PHÂN TÍCH SẢN PHẨM & BIẾN THỂ HOT GỐC dưới đây:
{master_context}
{extra_note_instruction}

Hãy viết THÊM 3 kịch bản quảng cáo mới hoàn toàn ở 3 góc tiếp cận mới.
TUÂN THỦ NGHIÊM NGẶT:
1. Khai thác đúng biến thể bán chạy nhất (Hero Variant) làm trọng tâm.
2. Sáng tạo nhân vật và bối cảnh linh hoạt, hoàn toàn mới mẻ, khớp tuyệt đối với ngữ cảnh câu thoại trong từng phân cảnh.
3. Mô tả hình ảnh nhân vật tương tác sản phẩm đúng 100% cơ chế vật lý thực tế.
4. Viết **Kịch bản Lời thoại Voiceover Tổng thể** ở đầu mỗi kịch bản, sau đó chia thành các phân cảnh 8 giây (32-40 chữ/cảnh).
5. Hoàn toàn KHÔNG TEXT, KHÔNG LOGO, KHÔNG NHẠC NỀN, KHÔNG TỪ NGỮ LIVESTREAM.
"""
                res_extra = model.generate_content(extra_prompt)
                st.session_state.script_3 = (st.session_state.script_3 or "") + "\n\n---\n\n" + clean_script_text(res_extra.text)
                st.session_state.prompts_s3 = None

                reconstructed_full = (
                    "---SPLIT_COL1_START---\n"
                    + (st.session_state.analysis_col1 or "")
                    + "\n---SPLIT_COL1_END---\n---SPLIT_COL2_START---\n"
                    + (st.session_state.analysis_col2 or "")
                    + "\n---SPLIT_COL2_END---\n---SPLIT_SCENE_1---\n"
                    + (st.session_state.script_1 or "")
                    + "\n---SPLIT_SCENE_2---\n"
                    + (st.session_state.script_2 or "")
                    + "\n---SPLIT_SCENE_3---\n"
                    + (st.session_state.script_3 or "")
                )
                save_project_db(
                    st.session_state.current_project_name,
                    (st.session_state.analysis_col1 or "") + "\n\n" + (st.session_state.analysis_col2 or ""),
                    reconstructed_full,
                )
                st.success("✅ Đã bổ sung thêm kịch bản mới và lưu vào Database thành công!")
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi: {e}")
