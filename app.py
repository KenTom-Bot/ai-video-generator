import datetime
import os
import sqlite3
import streamlit as st
import google.generativeai as genai
from PIL import Image

# --- 0. CẤU HÌNH HỆ THỐNG & BẢO MẬT ĐĂNG NHẬP ---
st.set_page_config(page_title="AI Video Viral", page_icon="🎬", layout="wide")

# Thiết lập mật khẩu bảo vệ App (Bạn có thể đổi mật khẩu tại đây)
ADMIN_PASSWORD = "123"  # <-- Mật khẩu truy cập app


def check_password():
  """Hàm kiểm tra trạng thái đăng nhập của người dùng"""

  def password_entered():
    if st.session_state["password"] == ADMIN_PASSWORD:
      st.session_state["password_correct"] = True
      del st.session_state["password"]
    else:
      st.session_state["password_correct"] = False

  if "password_correct" not in st.session_state:
    st.text_input(
        "🔒 Vui lòng nhập mật khẩu để truy cập App",
        type="password",
        on_change=password_entered,
        key="password",
    )
    st.warning("⚠️ App này được bảo mật. Vui lòng nhập mật khẩu để tiếp tục.")
    return False
  elif not st.session_state["password_correct"]:
    st.text_input(
        "🔒 Vui lòng nhập mật khẩu để truy cập App",
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


# --- 1. CẤU HÌNH DATABASE VĨNH VIỄN (SQLITE) ---
DB_FILE = "projects_database.db"


def init_db():
  """Hàm tạo bảng lưu trữ dự án nếu chưa tồn tại"""
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT,
            created_date TEXT,
            product_info TEXT,
            scripts TEXT,
            status TEXT,
            is_deleted INTEGER DEFAULT 0
        )
    """)
  conn.commit()
  conn.close()


init_db()


def save_project_db(
    project_name, product_info, scripts, status="Đã tạo kịch bản"
):
  """Hàm lưu hoặc cập nhật dự án vào Database"""
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  created_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  cursor.execute(
      """
        INSERT INTO projects (project_name, created_date, product_info, scripts, status, is_deleted)
        VALUES (?, ?, ?, ?, ?, 0)
    """,
      (project_name, created_date, product_info, scripts, status),
  )
  conn.commit()
  conn.close()


def get_all_projects():
  """Lấy danh sách tất cả dự án chưa bị xóa từ Database"""
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT id, project_name, created_date, product_info, scripts, status"
      " FROM projects WHERE is_deleted = 0 ORDER BY id DESC"
  )
  rows = cursor.fetchall()
  conn.close()
  return rows


def soft_delete_project(project_id):
  """Xóa mềm dự án"""
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE projects SET is_deleted = 1 WHERE id = ?", (project_id,)
  )
  conn.commit()
  conn.close()


# --- 2. KHỞI TẠO BIẾN SESSION STATE ---
if "current_project_name" not in st.session_state:
  st.session_state.current_project_name = (
      f"Dự án mới - {datetime.datetime.now().strftime('%d/%m/%Y')}"
  )
if "generated_scripts" not in st.session_state:
  st.session_state.generated_scripts = None
if "product_analysis" not in st.session_state:
  st.session_state.product_analysis = None
if "veo_prompts" not in st.session_state:
  st.session_state.veo_prompts = None

# --- 3. THANH ĐIỀU HƯỚNG (SIDEBAR) & QUẢN LÝ DỰ ÁN ---
st.sidebar.title("🗂️ Quản lý Dự án Vĩnh viễn")

# Nút Tạo dự án mới
if st.sidebar.button(
    "➕ Tạo Dự Án Mới", type="primary", use_container_width=True
):
  st.session_state.current_project_name = (
      f"Dự án mới - {datetime.datetime.now().strftime('%d/%m/%Y')}"
  )
  st.session_state.generated_scripts = None
  st.session_state.product_analysis = None
  st.session_state.veo_prompts = None
  st.rerun()

st.sidebar.divider()

# Ô Tên dự án chuyển sang thanh bên trái
st.sidebar.subheader("🏷️ Cài đặt Dự án")
project_title_input = st.sidebar.text_input(
    "Tên dự án hiện tại", value=st.session_state.current_project_name
)
st.session_state.current_project_name = project_title_input

st.sidebar.divider()

# Thanh tìm kiếm dự án cũ trong Database
search_query = st.sidebar.text_input("🔍 Tìm kiếm dự án cũ", "")
projects = get_all_projects()

st.sidebar.subheader("📜 Lịch sử dự án đã lưu")
if not projects:
  st.sidebar.info("Chưa có dự án nào trong Database.")
else:
  for pid, pname, pdate, pinfo, pscript, pstatus in projects:
    if search_query.lower() in pname.lower():
      col_p1, col_p2 = st.sidebar.columns([4, 1])
      if col_p1.button(f"📁 {pname[:22]}...", key=f"load_{pid}"):
        st.session_state.current_project_name = pname
        st.session_state.product_analysis = pinfo
        st.session_state.generated_scripts = pscript
        st.rerun()
      if col_p2.button("❌", key=f"del_{pid}"):
        soft_delete_project(pid)
        st.rerun()

# Đẩy nút Đăng xuất xuống dưới cùng của Sidebar
st.sidebar.markdown("<br><br><br>", unsafe_allow_html=True)
st.sidebar.divider()
if st.sidebar.button("🚪 Đăng xuất tài khoản", use_container_width=True):
  st.session_state["password_correct"] = False
  st.rerun()

# --- 4. GIAO DIỆN CHÍNH ---
st.title("🎬 AI Video Viral")
st.markdown(
    "Hệ thống tự động hóa 100% ngành hàng: AI tự phân tích ảnh sản phẩm,"
    " thông tin Shopee, khóa đồng bộ nhân vật, trang phục, giọng đọc Hà Nội"
    " chuẩn và sinh Prompt Veo 3 chuyên nghiệp."
)

# Gộp thành 1 ô tải ảnh duy nhất cho cả sản phẩm và thông tin
product_image = st.file_uploader(
    "1️⃣ Tải lên Ảnh Sản Phẩm Thật kèm thông tin chi tiết / thông số"
    " (Shopee/TikTok)",
    type=["jpg", "png", "jpeg"],
    help=(
        "Tải lên ảnh chụp sản phẩm rõ nét kèm thông tin mô tả để Veo 3 tham"
        " chiếu."
    ),
)

# Ô xem lại ảnh dạng ẩn (Collapsible)
if product_image:
  with st.expander("👁️ Xem lại ảnh đã tải lên (Bấm để mở/ẩn)"):
    st.image(
        product_image,
        caption="Ảnh sản phẩm & Thông tin đã tải lên",
        use_container_width=True,
    )

st.info(
    "💡 **Lưu ý:** Giới tính nhân vật, trang phục và chất giọng Hà Nội chuẩn"
    " sẽ được AI tự động phân tích và gán khớp tuyệt đối dựa trên đặc tính sản"
    " phẩm của bạn."
)

# --- 5. XỬ LÝ PHÂN TÍCH BẰNG GEMINI ---
if st.button(
    "🚀 Phân Tích Sản Phẩm & Tạo Bộ 3 Kịch Bản Ban Đầu", type="primary"
):
  if not product_image:
    st.error("Vui lòng tải lên ảnh sản phẩm thật kèm thông tin!")
  else:
    with st.spinner(
        "🤖 AI đang phân tích sản phẩm, tự động chọn nhân vật/giọng đọc và viết"
        " kịch bản..."
    ):
      try:
        # Tự động lấy API key từ cấu hình hệ thống bí mật của Streamlit Cloud (st.secrets)
        if "GEMINI_API_KEY" in st.secrets:
          genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        else:
          # Hoặc lấy từ biến môi trường nếu có
          genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

        model = genai.GenerativeModel("gemini-1.5-pro-latest")
        img_prod = Image.open(product_image)

        prompt_text = f"""
                Bạn là Giám đốc Sản xuất Video Quảng cáo AI chuyên nghiệp. Hãy phân tích ảnh sản phẩm kèm thông tin được cung cấp.
                Yêu cầu thực hiện:
                1. Tự động nhận diện chuẩn tên sản phẩm, chọn biến thể màu sắc chủ đạo (Hero Variant) dựa trên dấu hiệu bán chạy/lượt bán (nếu có).
                2. Tự động quyết định Giới tính/Nhân vật phù hợp nhất với ngành hàng (ví dụ: nam chủ xưởng cho cơ khí, nữ quản lý kho cho tiện ích, mẹ đi kèm bé cho đồ trẻ em, v.v.) và khóa chặt chất giọng Hà Nội chuẩn tương ứng.
                3. Thiết lập 6 Khóa đồng bộ: [CHARACTER_LOCK], [WARDROBE_LOCK], [BACKGROUND_LOCK], [VOICE_LOCK] (chuẩn Hà Nội), [PRODUCT_SCALE_&_COLOR_LOCK], [MECHANICS_&_PHYSICS_LOCK].
                4. Viết ra ĐẦU TIÊN BỘ 3 KỊCH BẢN THOẠI KHÁC NHAU ở 3 góc tiếp cận:
                   - Kịch bản 1: Góc Review Thực Tế / Xưởng tận gốc.
                   - Kịch bản 2: Góc Nỗi đau & Tình huống kịch tính.
                   - Kịch bản 3: Góc Flash Sale / Săn Sale sốc.
                Mỗi kịch bản phải có nhịp độ đọc nhanh dồn dập (32-42 từ/cảnh 8 giây), dùng từ ngữ dân dã, cuốn hút.
                """
        contents = [img_prod, prompt_text]

        response = model.generate_content(contents)
        st.session_state.generated_scripts = response.text
        st.session_state.product_analysis = "Đã phân tích thành công sản phẩm."

        # Tự động lưu vào Database vĩnh viễn
        save_project_db(
            st.session_state.current_project_name,
            st.session_state.product_analysis,
            st.session_state.generated_scripts,
        )
        st.success("✅ Phân tích thành công! Đã lưu vào Database vĩnh viễn.")
        st.rerun()
      except Exception as e:
        st.error(
            f"Lỗi khi gọi API (Hãy kiểm tra lại cấu hình GEMINI_API_KEY trên"
            f" Streamlit Cloud): {e}"
        )

# --- 6. HIỂN THỊ KỊCH BẢN & TÍNH NĂNG GỌI THÊM KỊCH BẢN ---
if st.session_state.generated_scripts:
  st.divider()
  st.subheader("📝 Kịch bản Thoại Đã Tạo (Chọn hoặc Gọi Thêm)")

  edited_scripts = st.text_area(
      "Bạn có thể đọc duyệt và chỉnh sửa trực tiếp lời thoại dưới đây:",
      value=st.session_state.generated_scripts,
      height=300,
  )
  st.session_state.generated_scripts = edited_scripts

  col_s1, col_s2 = st.columns(2)

  # Nút Gọi Thêm Kịch Bản (Góc tiếp cận mới / Flash Sale)
  if col_s1.button(
      "➕ Gọi thêm 3 Kịch bản khác (Góc tiếp cận mới & Flash Sale)",
      use_container_width=True,
  ):
    with st.spinner("🤖 AI đang sáng tạo thêm 3 góc tiếp cận mới..."):
      try:
        if "GEMINI_API_KEY" in st.secrets:
          genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        else:
          genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

        model = genai.GenerativeModel("gemini-1.5-pro-latest")
        extra_prompt = """
                Hãy viết THÊM 3 kịch bản quảng cáo mới hoàn toàn cho sản phẩm này ở 3 góc tiếp cận:
                1. Góc Flash Sale / Săn Sale sốc cuối tuần.
                2. Góc So sánh chất lượng với thị trường.
                3. Góc Trải nghiệm thực tế bất ngờ.
                Giữ nguyên nhịp đọc nhanh, khẩu ngữ dân dã, chia phân cảnh rõ ràng.
                """
        res_extra = model.generate_content(extra_prompt)
        st.session_state.generated_scripts += (
            "\n\n--- BỘ KỊCH BẢN MỚI BỔ SUNG ---\n\n" + res_extra.text
        )
        save_project_db(
            st.session_state.current_project_name,
            "Cập nhật thêm kịch bản",
            st.session_state.generated_scripts,
        )
        st.success("Đã bổ sung thêm 3 kịch bản mới thành công!")
        st.rerun()
      except Exception as e:
        st.error(f"Lỗi: {e}")

  # Nút Chuyển sang bước Chia Phân Cảnh & Xuất Prompt Veo 3
  if col_s2.button(
      "👉 Chốt Kịch Bản & Xuất Prompt Veo 3 Đồng Bộ",
      type="primary",
      use_container_width=True,
  ):
    with st.spinner("🤖 Đang chia phân cảnh động và khóa đồng bộ 6 lớp..."):
      try:
        if "GEMINI_API_KEY" in st.secrets:
          genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        else:
          genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

        model = genai.GenerativeModel("gemini-1.5-pro-latest")
        prompt_veo = f"""
                Dựa trên kịch bản đã duyệt sau đây:
                {st.session_state.generated_scripts}
                
                Hãy chia thành N phân cảnh (mỗi cảnh 8 giây). 
                Với mỗi phân cảnh, hãy xuất ra:
                1. [IMAGE PROMPT - CẢNH X]: Prompt tiếng Anh tạo ảnh gốc (Start Frame) giữ nguyên [CHARACTER_LOCK], [WARDROBE_LOCK], [BACKGROUND_LOCK], [PRODUCT_SCALE_&_COLOR_LOCK].
                2. [VEO 3 VIDEO PROMPT - CẢNH X]: Prompt tiếng Anh cho Veo 3 có gắn sẵn chuẩn giọng Hà Nội phù hợp, câu thoại tiếng Việt chuẩn trong ngoặc kép (đã phiên âm số/từ viết tắt thành chữ), kỹ thuật đọc ngoài khung hình (out-of-frame) cho cảnh cận, và âm thanh môi trường SFX.
                """
        res_v = model.generate_content(prompt_veo)
        st.session_state.veo_prompts = res_v.text
        save_project_db(
            st.session_state.current_project_name,
            "Đã xuất Prompt Veo 3",
            st.session_state.generated_scripts,
            status="Hoàn thành Prompt Veo 3",
        )
        st.success(
            "✅ Đã chia phân cảnh và xuất toàn bộ Prompt Veo 3 thành công!"
        )
      except Exception as e:
        st.error(f"Lỗi: {e}")

# --- 7. HIỂN THỊ KẾT QUẢ PROMPT VEO 3 (COPY 1 CHẠM) ---
if st.session_state.veo_prompts:
  st.divider()
  st.subheader("🎯 Bộ Prompt Veo 3 Hoàn Chỉnh (Đồng bộ tuyệt đối)")
  st.code(st.session_state.veo_prompts, language="text")
