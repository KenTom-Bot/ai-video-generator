import datetime
import os
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

ADMIN_PASSWORD = "123"  # Mật khẩu truy cập app


def check_password():
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


# --- 1. CẤU HÌNH KẾT NỐI SUPABASE DATABASE VĨNH VIỄN ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def save_project_db(
    project_name, product_info, scripts, status="Đã tạo kịch bản"
):
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


def get_all_projects():
  response = (
      supabase.table("projects")
      .select("id, project_name, created_date, product_info, scripts, status")
      .eq("is_deleted", 0)
      .order("id", desc=True)
      .execute()
  )
  rows = [
      (
          item["id"],
          item["project_name"],
          item["created_date"],
          item["product_info"],
          item["scripts"],
          item["status"],
      )
      for item in response.data
  ]
  return rows


def soft_delete_project(project_id):
  supabase.table("projects").update({"is_deleted": 1}).eq(
      "id", project_id
  ).execute()


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

# CHỈ HIỂN THỊ Ô UPLOAD KHI CHƯA CÓ KỊCH BẢN
if not st.session_state.generated_scripts:
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

  if analyze_btn:
    if not product_images:
      st.error("⚠️ Vui lòng tải lên ít nhất một ảnh sản phẩm!")
    else:
      with st.spinner(
          "🤖 AI đang phân tích toàn bộ các góc ảnh sản phẩm, khóa chặt biến thể"
          " Hot và viết kịch bản video dựng sẵn..."
      ):
        try:
          if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
          else:
            genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

          model = genai.GenerativeModel("gemini-3.8-flash")
          contents = [Image.open(img) for img in product_images]

          notes_instruction = (
              f"\n\n🚨 CHÚ Ý ĐẶC BIỆT (QUYỀN ƯU TIÊN CAO NHẤT): Người dùng đã nhập"
              f" ghi chú/yêu cầu riêng sau đây: '{user_notes}'. Bạn BẮT BUỘC"
              f" phải tuân thủ tuyệt đối, xoay xỏ nội dung và làm nổi bật các"
              f" yêu cầu này trong toàn bộ kịch bản và phân cảnh, vượt lên trên"
              f" các tiêu chuẩn thông thường nếu có xung đột."
              if user_notes.strip()
              else ""
          )

          prompt_text = f"""
                    Bạn là Giám đốc Sản xuất Video Quảng cáo AI chuyên nghiệp cho các nền tảng Video ngắn (Reels, TikTok, Shorts - DẠNG VIDEO DỰNG SẴN, KHÔNG PHẢI LIVESTREAM). Hãy phân tích toàn bộ các hình ảnh sản phẩm được cung cấp.
                    {notes_instruction}
                    
                    QUY TẮC VÀNG VỀ NGÔN TỪ:
                    - Đây là VIDEO QUẢNG CÁO DỰNG SẴN, tuyệt đối KHÔNG dùng ngôn từ hiểu nhầm thành Livestream (Cấm dùng: "mọi người ơi", "vào giỏ hàng phiên live", "chấm điểm đi", "thả tim trên màn hình live", "giảm theo suất có hạn").
                    
                    YÊU CẦU ĐẶC BIỆT:
                    - Dòng đầu tiên của phản hồi PHẢI ghi chính xác tên chuẩn của sản phẩm (Ví dụ: Tên sản phẩm: Áo sơ mi nam công sở...).
                    
                    YÊU CẦU ĐỊNH DẠNG (CỰC KỲ QUAN TRỌNG - KHÔNG DÙNG THẺ HTML THÔ):
                    Hãy trả về kết quả bằng định dạng Markdown sạch sẽ gồm các phần sau:
                    1. PHẦN PHÂN TÍCH CHI TIẾT SẢN PHẨM: Trình bày rõ ràng 4 mục:
                       - **1. Chân dung Khách hàng & Hook 3s**
                       - **2. KOC Chuẩn Việt, Stylist & Khóa Màu (Hero Variant Hot)**
                       - **3. Giải phẫu Sản phẩm & Khóa Hình học 3D**
                       - **4. Chuẩn Bối Cảnh & Mức Giá**
                    2. PHẦN 3 KỊCH BẢN THOẠI QUẢNG CÁO:
                       - **Kịch bản 1: Góc Review Thực Tế / Xưởng tận gốc** (kèm nội dung chi tiết nhịp đọc 32-42 từ/cảnh 8 giây)
                       - **Kịch bản 2: Góc Nỗi đau & Tình huống kịch tính** (kèm nội dung chi tiết)
                       - **Kịch bản 3: Góc Flash Sale / Săn Sale sốc** (kèm nội dung chi tiết)
                    """
          contents.append(prompt_text)

          response = model.generate_content(contents)
          st.session_state.generated_scripts = response.text

          extracted_name = "Dự án sản phẩm"
          for line in response.text.split("\n"):
            if "tên sản phẩm" in line.lower() or "sản phẩm:" in line.lower():
              extracted_name = (
                  line.split(":")[-1]
                  .replace("*", "")
                  .replace("**", "")
                  .strip()
              )
              break
          if len(extracted_name) > 35:
            extracted_name = extracted_name[:35] + "..."

          st.session_state.current_project_name = (
              f"{extracted_name} - {datetime.datetime.now().strftime('%d/%m/%Y')}"
          )

          save_project_db(
              st.session_state.current_project_name,
              "Phân tích hoàn tất",
              st.session_state.generated_scripts,
          )
          st.success("✅ Phân tích thành công! Đã lưu lên Supabase Cloud.")
          st.rerun()
        except Exception as e:
          st.error(f"Lỗi khi gọi API: {e}")

# --- 6. HIỂN THỊ KỊCH BẢN VÀ NÚT XUẤT PROMPT NGAY DƯỚI TỪNG KỊCH BẢN ---
if st.session_state.generated_scripts:
  st.markdown("<br>", unsafe_allow_html=True)
  st.markdown(
      "<h2 style='text-align: center; color: #4F46E5;'>🔍 Phân Tích Chi Tiết"
      " & Kịch Bản Quảng Cáo (Video Dựng Sẵn)</h2>",
      unsafe_allow_html=True,
  )
  st.markdown(
      "<p style='text-align: center;'>Bạn có thể xem chi tiết bên dưới. Mỗi kịch"
      " bản đều có nút xuất Prompt Veo 3 ngay bên dưới để thao tác nhanh:</p>",
      unsafe_allow_html=True,
  )
  st.markdown("<br>", unsafe_allow_html=True)

  with st.container():
    st.markdown(st.session_state.generated_scripts)

  st.markdown("<br>", unsafe_allow_html=True)
  st.markdown(
      "<h3 style='text-align: center; color: #10B981;'>🎯 Xuất Prompt Veo 3"
      " Cho Từng Kịch Bản</h3>",
      unsafe_allow_html=True,
  )

  col_btn1, col_btn2, col_btn3 = st.columns(3)

  with col_btn1:
    if st.button(
        "👉 Xuất Prompt Kịch bản 1", type="primary", use_container_width=True
    ):
      with st.spinner("🤖 Đang tạo Prompt Veo 3 cho Kịch bản 1..."):
        try:
          if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
          else:
            genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

          model = genai.GenerativeModel("gemini-3.8-flash")
          res_v = model.generate_content(
              f"Dựa vào nội dung sau (video ngắn dựng sẵn, không phải live), hãy chia thành N phân cảnh (mỗi cảnh 8 giây) và xuất Prompt Veo 3 đồng bộ tuyệt đối cho Kịch bản 1:\n{st.session_state.generated_scripts}"
          )
          st.session_state.veo_prompts = res_v.text
          st.success("✅ Đã xuất Prompt Veo 3 Kịch bản 1 thành công!")
          st.rerun()
        except Exception as e:
          st.error(f"Lỗi: {e}")

  with col_btn2:
    if st.button(
        "👉 Xuất Prompt Kịch bản 2", type="primary", use_container_width=True
    ):
      with st.spinner("🤖 Đang tạo Prompt Veo 3 cho Kịch bản 2..."):
        try:
          if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
          else:
            genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

          model = genai.GenerativeModel("gemini-3.8-flash")
          res_v = model.generate_content(
              f"Dựa vào nội dung sau (video ngắn dựng sẵn, không phải live), hãy chia thành N phân cảnh (mỗi cảnh 8 giây) và xuất Prompt Veo 3 đồng bộ tuyệt đối cho Kịch bản 2:\n{st.session_state.generated_scripts}"
          )
          st.session_state.veo_prompts = res_v.text
          st.success("✅ Đã xuất Prompt Veo 3 Kịch bản 2 thành công!")
          st.rerun()
        except Exception as e:
          st.error(f"Lỗi: {e}")

  with col_btn3:
    if st.button(
        "👉 Xuất Prompt Kịch bản 3", type="primary", use_container_width=True
    ):
      with st.spinner("🤖 Đang tạo Prompt Veo 3 cho Kịch bản 3..."):
        try:
          if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
          else:
            genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

          model = genai.GenerativeModel("gemini-3.8-flash")
          res_v = model.generate_content(
              f"Dựa vào nội dung sau (video ngắn dựng sẵn, không phải live), hãy chia thành N phân cảnh (mỗi cảnh 8 giây) và xuất Prompt Veo 3 đồng bộ tuyệt đối cho Kịch bản 3:\n{st.session_state.generated_scripts}"
          )
          st.session_state.veo_prompts = res_v.text
          st.success("✅ Đã xuất Prompt Veo 3 Kịch bản 3 thành công!")
          st.rerun()
        except Exception as e:
          st.error(f"Lỗi: {e}")

  st.markdown("<br>", unsafe_allow_html=True)
  st.markdown("---")

  st.markdown("#### ➕ Tạo Thêm Kịch Bản Mới (Góc Tiếp Cận Khác)")
  extra_user_notes = st.text_area(
      "📝 Ghi chú / Yêu cầu riêng cho lần gọi thêm này (Tùy chọn)",
      placeholder=(
          "Nhập yêu cầu riêng cho các kịch bản gọi thêm (Ví dụ: Tập trung vào độ"
          " bền, nhấn mạnh quà tặng kèm...)"
      ),
      key="extra_notes_input",
  )

  if st.button(
      "🚀 Gọi thêm 3 Kịch bản mới theo yêu cầu", use_container_width=True
  ):
    with st.spinner("🤖 AI đang sáng tạo thêm 3 góc tiếp cận mới..."):
      try:
        if "GEMINI_API_KEY" in st.secrets:
          genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        else:
          genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

        model = genai.GenerativeModel("gemini-3.8-flash")
        extra_note_instruction = (
            f"\n\n🚨 GHI CHÚ RIÊNG CHO LẦN NÀY: '{extra_user_notes}'."
            if extra_user_notes.strip()
            else ""
        )
        extra_prompt = f"""
                Hãy viết THÊM 3 kịch bản quảng cáo mới hoàn toàn cho sản phẩm này ở 3 góc tiếp cận mới (So sánh chất lượng, Trải nghiệm bất ngờ, Chuyên gia phân tích).
                {extra_note_instruction}
                LƯU Ý: Đây là video ngắn dựng sẵn, CẤM tuyệt đối dùng từ ngữ livestream. BẮT BUỘC tiếp tục bám sát và khai thác đúng biến thể Hot (Hero Variant) đã xác định trước đó.
                Giữ nguyên nhịp đọc nhanh, khẩu ngữ dân dã, chia phân cảnh rõ ràng dưới dạng Markdown sạch.
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
        st.success("Đã bổ sung thêm 3 kịch bản mới và cập nhật Supabase!")
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
  st.markdown(
      "Sao chép các Prompt dưới đây dán trực tiếp vào Veo 3 để tạo video:"
  )
  st.code(st.session_state.veo_prompts, language="text")
