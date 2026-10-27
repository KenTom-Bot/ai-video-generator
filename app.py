import datetime
import os
import sqlite3
import streamlit as st
import google.generativeai as genai
from PIL import Image

# --- 0. CẤU HÌNH HỆ THỐNG & BẢO MẬT ĐĂNG NHẬP ---
st.set_page_config(
    page_title="AI Video Viral",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
    st.markdown(
        "<h2 style='text-align: center; color: #4F46E5;'>🔒 Đăng Nhập Hệ Thống"
        " AI Video Viral</h2>",
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
      st.warning("⚠️ App này được bảo mật tuyệt đối.")
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


# --- 1. CẤU HÌNH DATABASE VĨNH VIỄN (SQLITE) ---
DB_FILE = "projects_database.db"


def init_db():
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
st.sidebar.markdown(
    "<h3 style='text-align: center;'>🗂️ Quản lý Dự án</h3>",
    unsafe_allow_html=True,
)

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

st.sidebar.markdown("🏷️ **Cài đặt Tên Dự Án**")
project_title_input = st.sidebar.text_input(
    "Tên dự án hiện tại",
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
      if col_p1.button(f"📁 {pname[:20]}...", key=f"load_{pid}"):
        st.session_state.current_project_name = pname
        st.session_state.product_analysis = pinfo
        st.session_state.generated_scripts = pscript
        st.rerun()
      if col_p2.button("❌", key=f"del_{pid}"):
        soft_delete_project(pid)
        st.rerun()

st.sidebar.markdown("<br><br><br>", unsafe_allow_html=True)
st.sidebar.divider()
if st.sidebar.button("🚪 Đăng xuất tài khoản", use_container_width=True):
  st.session_state["password_correct"] = False
  st.rerun()

# --- 4. GIAO DIỆN CHÍNH ---
st.markdown(
    "<h1 style='text-align: center; color: #1F2937;'>🎬 AI Video Viral</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align: center; color: #4B5563; font-size: 16px;'>Hệ thống"
    " tự động hóa 100% ngành hàng: Phân tích sản phẩm, khóa đồng bộ nhân vật,"
    " trang phục, giọng đọc Hà Nội chuẩn và sinh Prompt Veo 3 chuyên"
    " nghiệp.</p>",
    unsafe_allow_html=True,
)
st.divider()

st.markdown("### 📦 Thông Tin Đầu Vào Sản Phẩm")
product_images = st.file_uploader(
    "Tải lên nhiều ảnh sản phẩm thật (Nhiều góc độ, thông tin chi tiết,"
    " thông số...)",
    type=["jpg", "png", "jpeg"],
    accept_multiple_files=True,
    help=(
        "Bạn có thể chọn nhiều ảnh cùng lúc để AI phân tích toàn diện mọi góc"
        " cạnh của sản phẩm."
    ),
)

if product_images:
  with st.expander(
      f"👁️ Xem lại danh sách ảnh đã tải lên ({len(product_images)} ảnh) (Bấm để"
      " mở/ẩn)"
  ):
    cols = st.columns(min(len(product_images), 3))
    for idx, img_file in enumerate(product_images):
      with cols[idx % len(cols)]:
        st.image(
            img_file, caption=f"Ảnh {idx + 1}", use_container_width=True
        )

user_notes = st.text_area(
    "📝 Ghi chú / Yêu cầu riêng cho kịch bản (Quyền ưu tiên cao nhất)",
    placeholder=(
        "Nhập các yêu cầu đặc biệt của bạn vào đây (Ví dụ: Nhấn mạnh chương"
        " trình mua 1 tặng 1, tập trung vào chất liệu inox 304, hoặc đang chạy"
        " flash sale giảm 50%...)"
    ),
    help=(
        "Nếu bạn nhập nội dung vào ô này, AI sẽ ưu tiên tuyệt đối các yêu cầu"
        " này khi xây dựng toàn bộ kịch bản."
    ),
)

st.markdown(
    "<p style='text-align: center; color: #6B7280; font-style: italic;'>💡 Lưu"
    " ý: Giới tính nhân vật, trang phục và chất giọng Hà Nội chuẩn sẽ được AI"
    " tự động phân tích và gán khớp tuyệt đối dựa trên đặc tính sản"
    " phẩm.</p>",
    unsafe_allow_html=True,
)
st.markdown("<br>", unsafe_allow_html=True)

col_b1, col_b2, col_b3 = st.columns([1, 2, 1])
with col_b2:
  analyze_btn = st.button(
      "🚀 Phân Tích Sản Phẩm & Tạo Kịch Bản",
      type="primary",
      use_container_width=True,
  )

# --- 5. XỬ LÝ PHÂN TÍCH BẰNG GEMINI ---
if analyze_btn:
  if not product_images:
    st.error("⚠️ Vui lòng tải lên ít nhất một ảnh sản phẩm!")
  else:
    with st.spinner(
        "🤖 AI đang phân tích toàn bộ các góc ảnh sản phẩm, ưu tiên ghi chú và"
        " viết kịch bản..."
    ):
      try:
        if "GEMINI_API_KEY" in st.secrets:
          genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        else:
          genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

        model = genai.GenerativeModel("gemini-3.8-flash")
        contents = [Image.open(img) for img in product_images]

        notes_instruction = (
            f"\n\n🚨 CHÚ Ý ĐẶC BIỆT (QUYỀN ƯU TIÊN CAO NHẤT): Người dùng đã nhập ghi"
            f" chú/yêu cầu riêng sau đây: '{user_notes}'. Bạn BẮT BUỘC phải tuân"
            f" thủ tuyệt đối, xoay xỏ nội dung và làm nổi bật các yêu cầu này"
            f" trong toàn bộ kịch bản và phân cảnh, vượt lên trên các tiêu chuẩn"
            f" thông thường nếu có xung đột."
            if user_notes.strip()
            else ""
        )

        prompt_text = f"""
                Bạn là Giám đốc Sản xuất Video Quảng cáo AI chuyên nghiệp. Hãy phân tích toàn bộ các hình ảnh sản phẩm được cung cấp (bao gồm các góc độ, thông số, chi tiết khác nhau).
                {notes_instruction}
                
                Yêu cầu thực hiện:
                1. Tổng hợp thông tin từ tất cả các hình ảnh để nhận diện chuẩn tên sản phẩm, chọn biến thể màu sắc chủ đạo (Hero Variant) dựa trên dấu hiệu bán chạy/lượt bán (nếu có).
                2. Tự động quyết định Giới tính/Nhân vật phù hợp nhất với ngành hàng và khóa chặt chất giọng Hà Nội chuẩn tương ứng.
                3. Thiết lập 6 Khóa đồng bộ: [CHARACTER_LOCK], [WARDROBE_LOCK], [BACKGROUND_LOCK], [VOICE_LOCK] (chuẩn Hà Nội), [PRODUCT_SCALE_&_COLOR_LOCK], [MECHANICS_&_PHYSICS_LOCK].
                4. Viết ra ĐẦU TIÊN BỘ 3 KỊCH BẢN THOẠI KHÁC NHAU ở 3 góc tiếp cận (Định dạng rõ ràng Kịch bản 1, Kịch bản 2, Kịch bản 3):
                   - Kịch bản 1: Góc Review Thực Tế / Xưởng tận gốc.
                   - Kịch bản 2: Góc Nỗi đau & Tình huống kịch tính.
                   - Kịch bản 3: Góc Flash Sale / Săn Sale sốc.
                Mỗi kịch bản phải có nhịp độ đọc nhanh dồn dập (32-42 từ/cảnh 8 giây), dùng từ ngữ dân dã, cuốn hút.
                """
        contents.append(prompt_text)

        response = model.generate_content(contents)
        st.session_state.generated_scripts = response.text
        st.session_state.product_analysis = f"Ghi chú ưu tiên: {user_notes}"

        save_project_db(
            st.session_state.current_project_name,
            st.session_state.product_analysis,
            st.session_state.generated_scripts,
        )
        st.success("✅ Phân tích thành công! Đã lưu vào Database vĩnh viễn.")
        st.rerun()
      except Exception as e:
        st.error(f"Lỗi khi gọi API: {e}")

# --- 6. HIỂN THỊ KỊCH BẢN GỌN GÀNG, RÕ RÀNG THEO TỪNG TAB ---
if st.session_state.generated_scripts:
  st.markdown("<br>", unsafe_allow_html=True)
  st.markdown(
      "<h2 style='text-align: center; color: #4F46E5;'>📝 Kịch Bản Thoại Đã"
      " Tạo</h2>",
      unsafe_allow_html=True,
  )
  st.markdown(
      "<p style='text-align: center;'>Dưới đây là các kịch bản được chia theo"
      " góc tiếp cận. Bạn có thể xem, chỉnh sửa hoặc bấm trực tiếp nút xuất"
      " Prompt Veo 3 cho từng kịch bản:</p>",
      unsafe_allow_html=True,
  )

  # Cho phép chỉnh sửa tổng thể nếu muốn
  with st.expander("✏️ Mở rộng để chỉnh sửa toàn bộ nội dung kịch bản gốc"):
    edited_scripts = st.text_area(
        "Nội dung kịch bản thoại",
        value=st.session_state.generated_scripts,
        height=300,
    )
    st.session_state.generated_scripts = edited_scripts

  st.markdown("<br>", unsafe_allow_html=True)

  # Chia không gian hiển thị bằng 3 Tab tương ứng với 3 góc tiếp cận
  tab1, tab2, tab3 = st.tabs([
      "🎬 Kịch bản 1: Review Thực Tế",
      "🚨 Kịch bản 2: Nỗi Đau / Kịch Tính",
      "⚡ Kịch bản 3: Flash Sale Sốc",
  ])

  with tab1:
    st.markdown("#### Góc Review Thực Tế / Xưởng Tận Gốc")
    script_c1 = st.text_area(
        "Chỉnh sửa Kịch bản 1",
        value=st.session_state.generated_scripts,
        height=220,
        key="sc1",
    )
    if st.button(
        "👉 Chốt Kịch bản 1 & Xuất Prompt Veo 3",
        key="btn_c1",
        type="primary",
        use_container_width=True,
    ):
      with st.spinner("🤖 Đang tạo Prompt Veo 3 cho Kịch bản 1..."):
        try:
          if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
          else:
            genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

          model = genai.GenerativeModel("gemini-3.8-flash")
          res_v = model.generate_content(
              f"Dựa vào kịch bản sau, hãy chia thành N phân cảnh (mỗi cảnh 8 giây) và xuất Prompt Veo 3 đồng bộ tuyệt đối:\n{script_c1}"
          )
          st.session_state.veo_prompts = res_v.text
          st.success("✅ Đã xuất Prompt Veo 3 cho Kịch bản 1 thành công!")
          st.rerun()
        except Exception as e:
          st.error(f"Lỗi: {e}")

  with tab2:
    st.markdown("#### Góc Nỗi Đau & Tình Huống Kịch Tính")
    script_c2 = st.text_area(
        "Chỉnh sửa Kịch bản 2",
        value=st.session_state.generated_scripts,
        height=220,
        key="sc2",
    )
    if st.button(
        "👉 Chốt Kịch bản 2 & Xuất Prompt Veo 3",
        key="btn_c2",
        type="primary",
        use_container_width=True,
    ):
      with st.spinner("🤖 Đang tạo Prompt Veo 3 cho Kịch bản 2..."):
        try:
          if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
          else:
            genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

          model = genai.GenerativeModel("gemini-3.8-flash")
          res_v = model.generate_content(
              f"Dựa vào kịch bản sau, hãy chia thành N phân cảnh (mỗi cảnh 8 giây) và xuất Prompt Veo 3 đồng bộ tuyệt đối:\n{script_c2}"
          )
          st.session_state.veo_prompts = res_v.text
          st.success("✅ Đã xuất Prompt Veo 3 cho Kịch bản 2 thành công!")
          st.rerun()
        except Exception as e:
          st.error(f"Lỗi: {e}")

  with tab3:
    st.markdown("#### Góc Flash Sale / Săn Sale Sốc")
    script_c3 = st.text_area(
        "Chỉnh sửa Kịch bản 3",
        value=st.session_state.generated_scripts,
        height=220,
        key="sc3",
    )
    if st.button(
        "👉 Chốt Kịch bản 3 & Xuất Prompt Veo 3",
        key="btn_c3",
        type="primary",
        use_container_width=True,
    ):
      with st.spinner("🤖 Đang tạo Prompt Veo 3 cho Kịch bản 3..."):
        try:
          if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
          else:
            genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

          model = genai.GenerativeModel("gemini-3.8-flash")
          res_v = model.generate_content(
              f"Dựa vào kịch bản sau, hãy chia thành N phân cảnh (mỗi cảnh 8 giây) và xuất Prompt Veo 3 đồng bộ tuyệt đối:\n{script_c3}"
          )
          st.session_state.veo_prompts = res_v.text
          st.success("✅ Đã xuất Prompt Veo 3 cho Kịch bản 3 thành công!")
          st.rerun()
        except Exception as e:
          st.error(f"Lỗi: {e}")

  st.markdown("<br>", unsafe_allow_html=True)
  # Nút gọi thêm kịch bản mới
  if st.button(
      "➕ Gọi thêm 3 Kịch bản khác (Góc tiếp cận mới)",
      use_container_width=True,
  ):
    with st.spinner("🤖 AI đang sáng tạo thêm 3 góc tiếp cận mới..."):
      try:
        if "GEMINI_API_KEY" in st.secrets:
          genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        else:
          genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

        model = genai.GenerativeModel("gemini-3.8-flash")
        extra_notes_instruction = (
            f"\n\n🚨 GHI CHÚ ƯU TIÊN CAO NHẤT TỪ NGƯỜI DÙNG: '{user_notes}'."
            if user_notes.strip()
            else ""
        )
        extra_prompt = f"""
                Hãy viết THÊM 3 kịch bản quảng cáo mới hoàn toàn cho sản phẩm này ở 3 góc tiếp cận khác:
                1. Góc So sánh chất lượng với thị trường.
                2. Góc Trải nghiệm thực tế bất ngờ của khách hàng.
                3. Góc Chuyên gia ngành hàng phân tích.
                {extra_notes_instruction}
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

# --- 7. HIỂN THỊ KẾT QUẢ PROMPT VEO 3 (COPY 1 CHẠM) ---
if st.session_state.veo_prompts:
  st.markdown("<br>", unsafe_allow_html=True)
  st.markdown(
      "<h3 style='text-align: center; color: #10B981;'>🎯 Bộ Prompt Veo 3 Hoàn"
      " Chỉnh (Đồng bộ tuyệt đối)</h3>",
      unsafe_allow_html=True,
  )
  st.code(st.session_state.veo_prompts, language="text")
