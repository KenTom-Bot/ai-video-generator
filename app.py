import datetime
import os
import re
from io import BytesIO
import streamlit as st
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
MODEL_NAME = "gemini-3.8-flash"  # Đã chuyển sang bản gemini-3.8-flash theo yêu cầu


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


# --- 2. HÀM NÉN ẢNH & HÀM DỌN SẠCH KÝ TỰ RÁC ---
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
    "Hệ thống tự động hóa 100% đa ngành hàng: Quét biến thể Hot 🔥 & Lượt bán cao, phân tích chuẩn cơ chế hoạt động sản phẩm, "
    "khóa đồng nhất trang phục, giọng đọc Hà Nội (32-40 chữ/cảnh 8s) và xuất Prompt Ảnh & Video Veo 3."
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
        help="Chọn nhiều ảnh để AI quét chính xác lượt bán, biến thể Hot và hiểu rõ cơ chế hoạt động của sản phẩm.",
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
            "🚀 Phân Tích Chuyên Sâu & Tạo Kịch Bản Đa Ngành Hàng",
            type="primary",
            use_container_width=True,
        )

    if analyze_btn:
        if not product_images:
            st.error("⚠️ Vui lòng tải lên ít nhất một ảnh sản phẩm!")
        else:
            with st.spinner("🤖 AI (gemini-3.8-flash) đang quét lượt bán, biến thể Hot 🔥, phân tích cơ chế hoạt động và viết kịch bản..."):
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
Bạn là Giám đốc Sản xuất Video Quảng cáo AI chuyên nghiệp cho video ngắn dựng sẵn (Reels, TikTok - KHÔNG LIVESTREAM), am hiểu 100% các ngành hàng (Thời trang, Gia dụng, Điện tử, Mỹ phẩm, Sức khỏe, Thực phẩm, Phụ kiện, Mẹ & Bé...).
Hãy phân tích cực kỳ kỹ lưỡng tất cả các hình ảnh sản phẩm được tải lên.
{notes_instruction}

1. QUY TẮC BẮT BUỘC VỀ QUÉT LƯỢT BÁN & BIẾN THỂ BÁN CHẠY NHẤT (HERO VARIANT) + ĐỒNG NHẤT TRANG PHỤC:
- **Quét dữ liệu bán chạy toàn diện:** Bạn PHẢI đọc kỹ từng con chữ và biểu tượng trên tất cả ảnh chụp màn hình:
  + Tìm con số **Lượt bán** (Ví dụ: "Đã bán 1.2k", "Đã bán 5.4k", thanh tiến trình "Đang bán chạy", số lượng đánh giá từng phân loại).
  + Tìm các biểu tượng/nhãn như icon ngọn lửa 🔥, chữ "Hot", "Bán chạy", "Best Seller".
- **Chọn biến thể chủ lực (Hero Variant):** Biến thể/màu sắc/phân loại nào có **lượt bán cao nhất** hoặc có gắn **icon 🔥 / chữ Hot** (Ví dụ: "Đầm ĐEN-34D" có icon 🔥 Hot) BẮT BUỘC phải được chọn làm sản phẩm chủ lực xuyên suốt toàn bộ dự án (trừ khi Ghi chú người dùng yêu cầu khác).
- **KHÓA ĐỒNG NHẤT TRANG PHỤC 100% (MASTER OUTFIT LOCK):** Thiết lập cố định 100% ngoại hình KOC và bộ trang phục từ đầu đến cuối (quần, áo, váy, áo trong, áo khoác ngoài, kiểu tóc, giày dép, phụ kiện). Tất cả các phân cảnh BẮT BUỘC giữ nguyên bộ trang phục này, tuyệt đối không đổi quần áo hay giày dép giữa các cảnh.

2. PHÂN TÍCH KỸ CHỨC NĂNG, CẤU TẠO & CƠ CHẾ HOẠT ĐỘNG THỰC TẾ CỦA SẢN PHẨM (FUNCTIONAL & PHYSICS LOCK - ĐA NGÀNH HÀNG):
- Tự động nhận diện đúng ngành hàng của sản phẩm để mô tả chính xác tuyệt đối **cách thức hoạt động và thao tác sử dụng ngoài đời thực**:
  + *Nếu là Thời trang/May mặc:* Hiểu rõ cấu tạo (khóa tăng đơ trượt chỉnh dây thế nào, độ co giãn đàn hồi 4 chiều khi kéo tay ra sao, lớp lót trong, form ôm siết eo hay tùng xòe che bụng khi xoay người...).
  + *Nếu là Gia dụng/Điện tử/Đồ công nghệ:* Hiểu rõ cơ chế vận hành (cầm nắm ở bộ phận nào, bấm nút hay cảm ứng ở đâu, lắp ráp/tháo rời ra sao, tia nước/luồng gió/ánh sáng đèn hoạt động thế nào, kích thước thật so với bàn tay...).
  + *Nếu là Mỹ phẩm/Thực phẩm/Tiêu dùng:* Hiểu rõ kết cấu (dạng kem đặc, serum nhỏ giọt, xịt phun sương hay viên nén), cách mở nắp (vặn xoáy hay bật nắp), cách thoa/sử dụng lên da hoặc pha chế đúng quy trình.
- **Tuyệt đối không bịa đặt chức năng hoặc mô tả thao tác vật lý sai lệch** với cấu tạo thật của sản phẩm trên ảnh.

3. QUY TẮC 3 KHÔNG TUYỆT ĐỐI VỀ HÌNH ẢNH & ÂM THANH:
- CẤM dùng từ ngữ livestream ("mọi người ơi", "giỏ hàng phiên live", "vào phiên live", "chốt đơn trên live").
- CẤM hiển thị 3 câu hook riêng lẻ.
- **TUYỆT ĐỐI KHÔNG TEXT (NO TEXT OVERLAY), KHÔNG LOGO, KHÔNG NHẠC NỀN (NO BACKGROUND MUSIC)** trong toàn bộ mô tả phân cảnh, ảnh và video. Chỉ có giọng nói trực tiếp của nhân vật và âm thanh hiệu ứng vật lý thực tế của sản phẩm (SFX).

4. QUY TRÌNH SÁNG TẠO KỊCH BẢN CHUẨN XÁC:
- **Bước 1:** Ở đầu mỗi kịch bản, viết **Kịch bản Lời thoại Voiceover Tổng thể** liền mạch cho toàn bộ video (giọng Hà Nội tự nhiên, cuốn hút).
- **Bước 2:** Chia lời thoại tổng thể đó thành các **PHÂN CẢNH 8 GIÂY**.
- **Giới hạn chữ nghiêm ngặt:** Mỗi phân cảnh 8 giây **CHỈ ĐƯỢC CHỨA TỪ 32 ĐẾN TỐI ĐA 40 CHỮ** trong phần lời thoại để nhân vật nói vừa vặn, rõ chữ, không bị nói quá nhanh.
- **Linh hoạt số lượng phân cảnh:** Không dừng lại ở 3 phân cảnh cố định. Nếu kịch bản dài, hãy **tự động chia thành 4, 5 hoặc 6 phân cảnh** sao cho mỗi phân cảnh luôn giữ đúng chuẩn 32-40 chữ.
- **Cấu trúc hiển thị mỗi phân cảnh:** Dòng trên là `*Hình ảnh:*` (mô tả góc máy, thao tác sử dụng đúng cơ chế hoạt động của sản phẩm, giữ nguyên trang phục đã khóa, không text, không logo), dòng dưới là `*Lời thoại phân cảnh:*` (câu thoại 32-40 chữ của cảnh đó).

Dòng đầu tiên của câu trả lời PHẢI ghi chính xác: Tên sản phẩm: [Tên ngắn gọn của sản phẩm]

TRẢ VỀ KẾT QUẢ ĐÚNG THEO CÁC THẺ PHÂN TÁCH SAU (KHÔNG THÊM BẤT KỲ KÝ TỰ RÁC NÀO):
---SPLIT_COL1_START---
### 📌 Cột Trái: Phân Tích Lượt Bán, Biến Thể Hot 🔥 & Khóa Trang Phục
- **1. Ngành hàng, Lượt bán & Chân dung Khách hàng:**
  - *Ngành hàng & Dữ liệu lượt bán quét được:* [Ghi rõ tổng lượt bán, đánh giá hoặc chỉ số bán chạy đọc được từ ảnh]
  - *Chân dung khách hàng & Nỗi đau trọng tâm:* [Mô tả chi tiết]
- **2. Biến Thể Chủ Lực (Hero Variant Hot 🔥) & Khóa Đồng Nhất Trang Phục (Master Outfit Lock):**
  - *Biến thể bán chạy nhất được chọn:* [Ghi rõ tên/màu biến thể có lượt bán cao nhất hoặc có icon Hot 🔥]
  - *Ngoại hình KOC cố định:* [Độ tuổi, gương mặt, làn da, kiểu tóc cố định]
  - *Trang phục khóa chặt 100% (Áo/Váy/Quần/Áo khoác):* [Mô tả chi tiết từng món đồ trên người nhân vật]
  - *Giày dép & Phụ kiện khóa chặt 100%:* [Mô tả chi tiết giày/dép, phụ kiện cố định xuyên suốt mọi phân cảnh]
---SPLIT_COL1_END---

---SPLIT_COL2_START---
### 🎨 Cột Phải: Giải Phẫu Cơ Chế Hoạt Động & Bối Cảnh
- **3. Giải phẫu Cấu tạo 3D & Cơ chế Hoạt động Thực tế (Functional & Physics Lock):**
  - *Kích thước, Chất liệu & Cấu tạo 3D:* [Mô tả tỉ lệ thật, bề mặt chất liệu, các bộ phận chi tiết]
  - *Cách thức hoạt động & Thao tác sử dụng chuẩn:* [Mô tả chính xác cách tay nhân vật tương tác, vận hành hoặc trình diễn tính năng sản phẩm đúng vật lý thực tế]
- **4. Chuẩn Bối Cảnh Cố Định & Mức Giá Ưu Đãi:**
  - *Bối cảnh & Ánh sáng đồng nhất:* [Không gian phù hợp với ngành hàng sản phẩm]
  - *Thông tin Giá & Ưu đãi:* [Mức giá và ưu đãi đọc được từ ảnh]
---SPLIT_COL2_END---

---SPLIT_SCENE_1---
### 🎬 Kịch bản 1: Góc Review Thực Tế & Trình Diễn Tính Năng
- **Kịch bản Lời thoại Voiceover Tổng thể (Giọng Hà Nội chuẩn):** "[Viết toàn bộ lời thoại liền mạch của cả video tại đây]"
- **Phân cảnh 1 (8 giây):**
  - *Hình ảnh:* [Mô tả chi tiết góc máy, thao tác sản phẩm đúng cơ chế hoạt động, giữ nguyên 100% trang phục đã khóa, KHÔNG TEXT, KHÔNG LOGO]
  - *Lời thoại phân cảnh (32-40 chữ):* "[Câu thoại của phân cảnh 1]"
- **Phân cảnh 2 (8 giây):**
  - *Hình ảnh:* [Mô tả chi tiết góc máy, thao tác chứng minh công năng/chất liệu sản phẩm, giữ nguyên 100% trang phục đã khóa, KHÔNG TEXT, KHÔNG LOGO]
  - *Lời thoại phân cảnh (32-40 chữ):* "[Câu thoại của phân cảnh 2]"
- **Phân cảnh 3 (8 giây):**
  - *Hình ảnh:* [Mô tả chi tiết góc máy, giữ nguyên 100% trang phục đã khóa, KHÔNG TEXT, KHÔNG LOGO]
  - *Lời thoại phân cảnh (32-40 chữ):* "[Câu thoại của phân cảnh 3]"
(Tiếp tục thêm Phân cảnh 4, Phân cảnh 5... nếu lời thoại tổng thể còn nội dung)

---SPLIT_SCENE_2---
### 🎬 Kịch bản 2: Góc Giải Quyết Nỗi Đau & Tình Huống Thực Tế
- **Kịch bản Lời thoại Voiceover Tổng thể (Giọng Hà Nội chuẩn):** "[Viết toàn bộ lời thoại liền mạch của cả video tại đây]"
- **Phân cảnh 1 (8 giây):**
  - *Hình ảnh:* [Mô tả chi tiết cảnh quay đúng cơ chế sản phẩm, giữ nguyên 100% trang phục đã khóa, KHÔNG TEXT, KHÔNG LOGO]
  - *Lời thoại phân cảnh (32-40 chữ):* "[Câu thoại của phân cảnh 1]"
- **Phân cảnh 2 (8 giây):**
  - *Hình ảnh:* [...]
  - *Lời thoại phân cảnh (32-40 chữ):* "[...]"
- **Phân cảnh 3 (8 giây):**
  - *Hình ảnh:* [...]
  - *Lời thoại phân cảnh (32-40 chữ):* "[...]"
(Tiếp tục thêm Phân cảnh 4, 5... nếu cần)

---SPLIT_SCENE_3---
### 🎬 Kịch bản 3: Góc Kiểm Chứng Chất Lượng & Ưu Đãi Sốc
- **Kịch bản Lời thoại Voiceover Tổng thể (Giọng Hà Nội chuẩn):** "[Viết toàn bộ lời thoại liền mạch của cả video tại đây]"
- **Phân cảnh 1 (8 giây):**
  - *Hình ảnh:* [Mô tả chi tiết cảnh quay đúng cơ chế sản phẩm, giữ nguyên 100% trang phục đã khóa, KHÔNG TEXT, KHÔNG LOGO]
  - *Lời thoại phân cảnh (32-40 chữ):* "[Câu thoại của phân cảnh 1]"
- **Phân cảnh 2 (8 giây):**
  - *Hình ảnh:* [...]
  - *Lời thoại phân cảnh (32-40 chữ):* "[...]"
- **Phân cảnh 3 (8 giây):**
  - *Hình ảnh:* [...]
  - *Lời thoại phân cảnh (32-40 chữ):* "[...]"
(Tiếp tục thêm Phân cảnh 4, 5... nếu cần)
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
                    st.success("✅ Phân tích thành công theo Lượt bán & Biến thể Hot 🔥, đã lưu lên Supabase!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi khi gọi API: {e}")

# --- 6. HIỂN THỊ GIAO DIỆN 2 CỘT ĐỐI XỨNG & XUẤT PROMPT CHUẨN MẪU ---
if st.session_state.analysis_col1:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        "<h2 style='text-align: center; color: #4F46E5;'>🔍 Phân Tích Lượt Bán, Cơ Chế Hoạt Động & Khóa Trang Phục</h2>",
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
        "<h2 style='text-align: center; color: #4F46E5;'>🎬 Kịch Bản Quảng Cáo & Xuất Prompt Ảnh / Video Veo 3</h2>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    def handle_script_section(script_title, script_content, state_key):
        if not script_content:
            return
        st.markdown(script_content)

        if st.button(
            f"👉 Xuất Bộ Prompt Ảnh & Video Veo 3 cho {script_title} (Chuẩn Cơ Chế Sản Phẩm & Đồng Nhất Trang Phục)",
            key=f"btn_{state_key}",
            type="primary",
            use_container_width=True,
        ):
            with st.spinner(f"🤖 Đang tạo bộ Prompt Ảnh & Video Veo 3 (Khóa trang phục, cơ chế hoạt động & thoại) cho {script_title}..."):
                try:
                    configure_genai()
                    model = genai.GenerativeModel(MODEL_NAME)

                    master_context = f"{st.session_state.analysis_col1}\n{st.session_state.analysis_col2}"
                    prompt_gen = f"""
Dựa vào THÔNG TIN KHÓA TRANG PHỤC, BIẾN THỂ HOT & CƠ CHẾ HOẠT ĐỘNG SẢN PHẨM dưới đây:
{master_context}

Và nội dung {script_title} dưới đây:
{script_content}

Hãy xuất bộ Prompt tạo Ảnh tĩnh (Midjourney/Flux) và Prompt tạo Video (Veo 3 Pro) cho TẤT CẢ CÁC PHÂN CẢNH có trong kịch bản trên (kịch bản có bao nhiêu cảnh thì phải xuất đủ bấy nhiêu cảnh).

YÊU CẦU NGHIÊM NGẶT:
1. **ĐỒNG NHẤT TRANG PHỤC & NHÂN VẬT 100% (IDENTICAL CHARACTER & OUTFIT):** Trong MỌI câu lệnh `IMG_PROMPT` và `VID_PROMPT` của tất cả các cảnh, BẮT BUỘC mô tả lặp lại đầy đủ và y hệt 100% ngoại hình nhân vật, kiểu tóc, toàn bộ trang phục (quần, áo, váy, áo trong, áo ngoài, giày dép, phụ kiện) và bối cảnh để các cảnh nối tiếp nhau đồng nhất tuyệt đối.
2. **ĐÚNG CƠ CHẾ VẬT LÝ & CHỨC NĂNG SẢN PHẨM (ACCURATE PRODUCT MECHANICS & PHYSICS):** Mô tả chính xác tỉ lệ kích thước sản phẩm, chất liệu và cách bàn tay/cơ thể nhân vật tương tác hoặc vận hành sản phẩm đúng thực tế trong từng cảnh quay.
3. **TUYỆT ĐỐI KHÔNG TEXT, KHÔNG LOGO, KHÔNG NHẠC NỀN:** Luôn gắn cụm `no text, no words, no watermark, no logo` ở cuối prompt ảnh, và `no background music, no text overlay, no logo, studio quality audio` ở prompt video.
4. **NHÂN VẬT TRỰC TIẾP THOẠI TRONG VIDEO (VEO 3 LIP-SYNC DIALOGUE):** Trong `VID_PROMPT`, bắt buộc có chỉ dẫn nhân vật nói trực tiếp câu thoại tiếng Việt của phân cảnh đó với giọng nữ Hà Nội tự nhiên, khớp khẩu hình miệng (Ví dụ: `The Vietnamese female KOC speaks naturally in a clear Hanoi accent with accurate lip-sync, saying: "[Chèn nguyên văn câu thoại tiếng Việt 32-40 chữ của phân cảnh đó]"`), đi kèm âm thanh vật lý thực tế của sản phẩm (realistic product SFX).

BẮT BUỘC TRẢ VỀ ĐÚNG ĐỊNH DẠNG SAU CHO TỪNG PHÂN CẢNH:
===SCENE_SPLIT===
SCENE_NUM: [Số thứ tự cảnh, ví dụ: 1]
VOICE_LINE: [Nguyên văn câu lời thoại tiếng Việt của phân cảnh này]
IMG_PROMPT: [IDENTICAL SETTING & OUTFIT]: Vertical 9:16 photorealistic medium shot, [Mô tả chi tiết ngoại hình KOC + toàn bộ trang phục váy/áo/quần/giày dép cố định + cấu tạo 3D sản phẩm + hành động tương tác đúng chức năng], 8k resolution, photorealistic, no text, no logo --ar 9:16
VID_PROMPT: [PRODUCT-CENTRIC CAMERA & IDENTICAL OUTFIT]: Vertical 9:16 stable cinematic shot, [Mô tả chi tiết ngoại hình KOC + toàn bộ trang phục cố định + chuyển động sử dụng/trình diễn sản phẩm đúng cơ chế vật lý mượt mà]. The character speaks directly with natural facial expressions and accurate lip-sync in a clear Vietnamese Hanoi female voice, saying: "[Nguyên văn câu lời thoại tiếng Việt của phân cảnh này]". Studio quality voice audio, realistic product interaction sound effects, no background music, no text, no logo, anti-stutter.
"""
                    res = model.generate_content(prompt_gen)
                    st.session_state[state_key] = res.text
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi khi tạo Prompt: {e}")

        p_text = st.session_state.get(state_key)
        if p_text:
            st.markdown(f"<br><h4>🎯 Bộ Prompt Tinh Gọn Cho {script_title} (Bấm biểu tượng góc phải ô để Copy)</h4>", unsafe_allow_html=True)
            scenes = p_text.split("===SCENE_SPLIT===")
            scene_idx = 0
            for sc in scenes:
                if not sc.strip():
                    continue
                scene_idx += 1
                s_num = str(scene_idx)
                v_line = ""
                img_p = ""
                vid_p = ""

                for line in sc.strip().split("\n"):
                    line_clean = line.strip()
                    if line_clean.startswith("SCENE_NUM:"):
                        s_num = line_clean.replace("SCENE_NUM:", "").strip()
                    elif line_clean.startswith("VOICE_LINE:"):
                        v_line = line_clean.replace("VOICE_LINE:", "").strip().strip('"')
                    elif line_clean.startswith("IMG_PROMPT:"):
                        img_p = line_clean.replace("IMG_PROMPT:", "").strip()
                    elif line_clean.startswith("VID_PROMPT:"):
                        vid_p = line_clean.replace("VID_PROMPT:", "").strip()

                if v_line:
                    st.markdown(
                        f"<div style='background-color: #ECFDF5; border: 1px solid #A7F3D0; color: #047857; "
                        f"padding: 14px 18px; border-radius: 8px; margin-bottom: 12px; font-weight: 500;'>"
                        f"🗣️ <b>Lời thoại Cảnh {s_num}:</b> {v_line}</div>",
                        unsafe_allow_html=True,
                    )

                p_col1, p_col2 = st.columns(2)
                with p_col1:
                    st.markdown(f"🖼️ **Prompt Ảnh Tinh Gọn Cảnh {s_num} (Midjourney / Flux):**")
                    st.code(img_p if img_p else sc.strip(), language="text")
                with p_col2:
                    st.markdown(f"🎥 **Prompt Video Tinh Gọn Cảnh {s_num} (Veo 3 Pro - Âm thanh Studio, Chống Vấp Thoại):**")
                    st.code(vid_p if vid_p else sc.strip(), language="text")

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
        with st.spinner("🤖 AI đang sáng tạo thêm 3 kịch bản mới bám sát cơ chế sản phẩm & trang phục..."):
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
Dựa trên BẢNG PHÂN TÍCH SẢN PHẨM, CƠ CHẾ HOẠT ĐỘNG & KHÓA ĐỒNG NHẤT TRANG PHỤC GỐC dưới đây:
{master_context}
{extra_note_instruction}

Hãy viết THÊM 3 kịch bản quảng cáo mới hoàn toàn ở 3 góc tiếp cận mới (So sánh chất lượng, Trải nghiệm thực tế, Chuyên gia phân tích).
TUÂN THỦ NGHIÊM NGẶT:
1. Khai thác đúng biến thể bán chạy nhất (Hero Variant) và GIỮ NGUYÊN 100% BỘ TRANG PHỤC/GIÀY DÉP ĐÃ KHÓA xuyên suốt mọi phân cảnh.
2. Mô tả hình ảnh nhân vật tương tác và sử dụng sản phẩm đúng 100% với chức năng và cơ chế hoạt động vật lý thực tế.
3. Viết **Kịch bản Lời thoại Voiceover Tổng thể** ở đầu mỗi kịch bản, sau đó chia thành các phân cảnh 8 giây.
4. Mỗi phân cảnh 8 giây CHỈ CHỨA 32-40 CHỮ. Nếu dài phải tự động chia thành 4, 5 hoặc 6 phân cảnh.
5. Cấu trúc mỗi phân cảnh: `*Hình ảnh:*` ở trên, `*Lời thoại phân cảnh (32-40 chữ):*` ở dưới.
6. Hoàn toàn KHÔNG TEXT, KHÔNG LOGO, KHÔNG NHẠC NỀN, KHÔNG TỪ NGỮ LIVESTREAM.
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
