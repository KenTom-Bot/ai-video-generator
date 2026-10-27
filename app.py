import datetime
import os
import sqlite3
import streamlit as st
import google.generativeai as genai
from PIL import Image

# --- 0. CẤU HÌNH HỆ THỐNG & BẢO MẬT ĐĂNG NHẬP ---
st.set_page_config(
    page_title="AI Video Script & Prompt Generator", page_icon="🎬", layout="wide"
)

# Thiết lập mật khẩu bảo vệ App (Bạn có thể đổi mật khẩu tại đây)
ADMIN_PASSWORD = "123"  # <-- Đổi mật khẩu của bạn tại đây


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
  """Xóa mềm dự án (chuyển trạng thái is_deleted = 1)"""
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

if st.sidebar.button("🚪 Đăng xuất tài khoản", use_container_width=True):
  st.session_state["password_correct"] = False
  st.rerun()

st.sidebar.divider()

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

# --- 4. GIAO DIỆN CHÍNH ---
st.title("🎬 AI Video Script & Veo 3 Prompt Generator")
st.markdown(
    "Hệ thống tự động hóa 100% ngành hàng: Phân tích sản phẩm, khóa đồng bộ"
    " nhân vật, trang phục, giọng đọc Hà Nội chuẩn và sinh Prompt Veo 3 chuyên"
    " nghiệp."
)

api_key = st.text_input(
    "🔑 Nhập Google Gemini API Key của bạn", type="password"
)

col1, col2 = st.columns(2)
with col1:
  product_image = st.file_uploader(
      "1️⃣ Tải lên Ảnh Sản Phẩm Thật", type=["jpg", "png", "jpeg"]
  )
with col2:
  info_image = st.file_uploader(
      "2️⃣ Tải lên Ảnh Thông Tin/Thông số (Shopee/TikTok)",
      type=["jpg", "png", "jpeg"],
  )

if product_image or info_image:
  with st.expander("👁️ Xem lại ảnh đã tải lên (Bấm để mở/ẩn)"):
    sub_c1, sub_c2 = st.columns(2)
    if product_image:
      sub_c1.image(
          product_image, caption="Ảnh sản phẩm", use_container_width=True
      )
    if info_image:
      sub_c2.image(
          info_image, caption="Ảnh thông tin Shopee", use_container_width=True
      )

col_opt1, col_opt2, col_opt3 = st.columns(3)
with col_opt1:
  target_gender = st.selectbox(
      "👤 Giới tính / Nhân vật",
      [
          "Nam chủ xưởng (Cơ khí/Gia dụng nặng)",
          "Nữ nhân viên kho (Tiện ích/Điện tử)",
          "Nam/Nữ trẻ (Thời trang/Mỹ phẩm)",
          "Ông/Bà phúc hậu (Đồ người già)",
          "Cặp Mẹ & Bé (Đồ trẻ em)",
      ],
  )
with col_opt2:
  voice_accent = st.selectbox(
      "🗣️ Giọng đọc chuẩn",
      [
          "100% Giọng Hà Nội chuẩn (Nam trung niên hào sảng)",
          "100% Giọng Hà Nội chuẩn (Nữ nhân viên thân thiện)",
          "100% Giọng Hà Nội chuẩn (Người cao tuổi uy tín)",
      ],
  )
with col_opt3:
  project_title_input = st.text_input(
      "🏷️ Tên dự án", value=st.session_state.current_project_name
  )
  st.session_state.current_project_name = project_title_input

# --- 5. XỬ LÝ PHÂN TÍCH BẰNG GEMINI ---
if st.button(
    "🚀 Phân Tích Sản Phẩm & Tạo Bộ 3 Kịch Bản Ban Đầu", type="primary"
):
  if not api_key:
    st.error("Vui lòng nhập Gemini API Key để tiếp tục!")
  elif not product_image:
    st.error("Vui lòng tải lên ít nhất ảnh sản phẩm!")
  else:
    with st.spinner(
        "🤖 AI đang phân tích cơ học, chọn biến thể bán chạy và viết kịch bản..."
    ):
      try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-pro-latest")

        img_prod = Image.open(product_image)
        prompt_text = f"""
                Hãy phân tích ảnh sản phẩm và ảnh thông tin được cung cấp.
                Yêu cầu thực hiện:
                1. Nhận diện chuẩn tên sản phẩm, chọn biến thể màu sắc chủ đạo (Hero Variant) nếu có nhiều màu.
                2. Thiết lập 6 Khóa đồng bộ: [CHARACTER_LOCK], [WARDROBE_LOCK], [BACKGROUND_LOCK], [VOICE_LOCK] (chuẩn Hà Nội), [PRODUCT_SCALE_&_COLOR_LOCK], [MECHANICS_&_PHYSICS_LOCK].
                3. Viết ra ĐẦU TIÊN BỘ 3 KỊCH BẢN THOẠI KHÁC NHAU ở 3 góc tiếp cận:
                   - Kịch bản 1: Góc Review Thực Tế / Xưởng tận gốc.
                   - Kịch bản 2: Góc Nỗi đau & Tình huống kịch tính.
                   - Kịch bản 3: Góc Flash Sale / Săn Sale sốc.
                """
        contents = [img_prod, prompt_text]
        if info_image:
          contents.append(Image.open(info_image))

        response = model.generate_content(contents)
        st.session_state.generated_scripts = response.text
        st.session_state.product_analysis = "Đã phân tích thành công sản phẩm."

        save_project_db(
            st.session_state.current_project_name,
            st.session_state.product_analysis,
            st.session_state.generated_scripts,
        )
        st.success("✅ Phân tích thành công! Đã lưu vào Database.")
        st.rerun()
      except Exception as e:
        st.error(f"Lỗi khi gọi API: {e}")

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

  if col_s1.button(
      "➕ Gọi thêm 3 Kịch bản khác (Góc tiếp cận mới & Flash Sale)",
      use_container_width=True,
  ):
    if not api_key:
      st.error("Vui lòng nhập API Key!")
    else:
      with st.spinner("🤖 AI đang sáng tạo thêm 3 góc tiếp cận mới..."):
        try:
          genai.configure(api_key=api_key)
          model = genai.GenerativeModel("gemini-1.5-pro-latest")
          extra_prompt = """
                    Hãy viết THÊM 3 kịch bản quảng cáo mới hoàn toàn cho sản phẩm này ở 3 góc tiếp cận:
                    1. Góc Flash Sale / Săn Sale sốc cuối tuần.
                    2. Góc So sánh chất lượng với thị trường.
                    3. Góc Trải nghiệm thực tế bất ngờ.
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

  if col_s2.button(
      "👉 Chốt Kịch Bản & Xuất Prompt Veo 3 Đồng Bộ",
      type="primary",
      use_container_width=True,
  ):
    with st.spinner("🤖 Đang chia phân cảnh động và khóa đồng bộ 6 lớp..."):
      try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-pro-latest")
        prompt_veo = f"""
                Dựa trên kịch bản đã duyệt sau đây:
                {st.session_state.generated_scripts}
                Hãy chia thành N phân cảnh (mỗi cảnh 8 giây), xuất ra Prompt ảnh gốc và Prompt Veo 3 có gắn chuẩn [HANOI_VOICE_LOCK] và khẩu hình out-of-frame.
                """
        res_v = model.generate_content(prompt_veo)
        st.session_state.veo_prompts = res_v.text
        save_project_db(
            st.session_state.current_project_name,
            "Đã xuất Prompt Veo 3",
            st.session_state.generated_scripts,
            status="Hoàn thành Prompt Veo 3",
        )
        st.success("✅ Đã xuất toàn bộ Prompt Veo 3 thành công!")
      except Exception as e:
        st.error(f"Lỗi: {e}")

# --- 7. HIỂN THỊ KẾT QUẢ PROMPT VEO 3 ---
if st.session_state.veo_prompts:
  st.divider()
  st.subheader("🎯 Bộ Prompt Veo 3 Hoàn Chỉnh (Đồng bộ tuyệt đối)")
  st.code(st.session_state.veo_prompts, language="text")
