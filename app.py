import datetime
import os
from io import BytesIO
import streamlit as st
import google.generativeai as genai
from PIL import Image
from supabase import create_client, Client

# --- 0. CẤU HÌNH HỆ THỐNG & BẢO MẬT ĐĂng NHẬP ---
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
  except Exception:
    return []


def soft_delete_project(project_id):
  try:
    supabase.table("projects").update({"is_deleted": 1}).eq(
        "id", project_id
    ).execute()
  except Exception:
    pass


# --- 2. HÀM NÉN ẢNH TỐI ƯU TOKEN ---
def compress_image_for_ai(image_file, max_size=1024, quality=80):
  img = Image.open(image_file)
  if img.mode in ("RGBA", "P"):
    img = img.convert("RGB")
  img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
  buffer = BytesIO()
  img.save(buffer, format="JPEG", quality=quality, optimize=True)
  buffer.seek(0)
  return Image.open(buffer)


# --- 3. KHỞI TẠO BIẾN SESSION STATE ---
if "current_project_name" not in st.session_state:
  st.session_state.current_project_name = (
      f"Dự án mới - {datetime.datetime.now().strftime('%d/%m/%Y')}"
  )
if "product_analysis" not in st.session_state:
  st.session_state.product_analysis = None
if "script_1" not in st.session_state:
  st.session_state.script_1 = None
if "script_2" not in st.session_state:
  st.session_state.script_2 = None
if "script_3" not in st.session_state:
  st.session_state.script_3 = None
if "veo_prompts" not in st.session_state:
  st.session_state.veo_prompts = None

# --- 4. THANH ĐIỀU HƯỚNG (SIDEBAR) & QUẢN LÝ DỰ ÁN ---
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
  st.session_state.product_analysis = None
  st.session_state.script_1 = None
  st.session_state.script_2 = None
  st.session_state.script_3 = None
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
        try:
          parts = pscript.split("---SPLIT_SCENE_")
          st.session_state.script_1 = parts[1] if len(parts) > 1 else ""
          st.session_state.script_2 = parts[2] if len(parts) > 2 else ""
          st.session_state.script_3 = parts[3] if len(parts) > 3 else ""
        except Exception:
          st.session_state.script_1 = pscript
        st.rerun()
      if col_p2.button("❌", key=f"del_{pid}"):
        soft_delete_project(pid)
        st.rerun()

st.sidebar.markdown("<br><br><br>", unsafe_allow_html=True)
st.sidebar.divider()
if st.sidebar.button("🚪 Đăng xuất tài khoản", use_container_width=True):
  st.session_state["password_correct"] = False
  st.rerun()

# --- 5. GIAO DIỆN CHÍNH ---
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

if not st.session_state.product_analysis:
  st.markdown("### 📦 Thông Tin Đầu Vào Sản Phẩm")
  product_images = st.file_uploader(
      "Tải lên nhiều ảnh sản phẩm thật (Nhiều góc độ, thông tin chi tiết,"
      " thông số...)",
      type=["jpg", "png", "jpeg"],
      accept_multiple_files=True,
      help="Chọn nhiều ảnh cùng lúc để AI phân tích toàn diện sản phẩm.",
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
          " trình mua 1 tặng 1, tập trung vào chất liệu inox 304...)"
      ),
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
          "🤖 AI đang nén ảnh tối ưu token, phân tích biến thể Hot và viết"
          " kịch bản chuẩn..."
      ):
        try:
          if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
          else:
            genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

          model = genai.GenerativeModel("gemini-3.8-flash")
          contents = [compress_image_for_ai(img) for img in product_images]

          notes_instruction = (
              f"\n\n🚨 GHI CHÚ RIÊNG: '{user_notes}'."
              if user_notes.strip()
              else ""
          )

          prompt_text = f"""
                    Bạn là Giám đốc Sản xuất Video Quảng cáo AI chuyên nghiệp cho video ngắn dựng sẵn (Reels, TikTok - KHÔNG LIVESTREAM). Hãy phân tích các hình ảnh sản phẩm.
                    {notes_instruction}
                    
                    QUY TẮC CẤM TUYỆT ĐỐI:
                    - CẤM dùng từ ngữ livestream ("mọi người ơi", "giỏ hàng phiên live", "giảm theo suất", "vào giỏ hàng").
                    - CẤM hiển thị phần 3 câu hook giữ chân người xem.
                    - BẮT BUỘC khóa chặt vào biến thể bán chạy nhất (Hero Variant) đã xác định xuyên suốt các kịch bản.
                    
                    QUY TRÌNH SÁNG TẠO KỊCH BẢN CHUẨN:
                    1. Viết kịch bản LỜI THOẠI (Voiceover) chuẩn trước với nhịp đọc nhanh dồn dập (32-42 từ).
                    2. Dựa trực tiếp vào lời thoại đó để chia ra các PHÂN CẢNH, mỗi phân cảnh có thời lượng cố định chuẩn **8 giây**.
                    
                    Dòng đầu tiên PHẢI ghi chính xác tên sản phẩm (Ví dụ: Tên sản phẩm: Đầm body...).
                    
                    TRẢ VỀ KẾT QUẢ ĐÚNG THEO CẤU TRÚC PHÂN TÁCH SAU (SỬ DỤNG CHÍNH XÁC CÁC THẺ NÀY):
                    ---SPLIT_ANALYZE---
                    ### 🔍 Phân Tích Chi Tiết Sản Phẩm
                    - **1. Chân dung Khách hàng & Đặc tính:** ...
                    - **2. KOC Chuẩn Việt, Stylist & Khóa Màu (Hero Variant Hot):** ...
                    - **3. Giải phẫu Sản phẩm & Khóa Hình học 3D:** ...
                    - **4. Chuẩn Bối Cảnh & Mức Giá:** ...
                    
                    ---SPLIT_SCENE_1---
                    ### 🎬 Kịch bản 1: Góc Review Thực Tế / Xưởng tận gốc
                    - **Kịch bản Lời thoại Voiceover:** [...]
                    - **Phân cảnh 1 (8 giây):** [...]
                    - **Phân cảnh 2 (8 giây):** [...]
                    - **Phân cảnh 3 (8 giây):** [...]
                    
                    ---SPLIT_SCENE_2---
                    ### 🎬 Kịch bản 2: Góc Nỗi đau & Tình huống kịch tính
                    - **Kịch bản Lời thoại Voiceover:** [...]
                    - **Phân cảnh 1 (8 giây):** [...]
                    - **Phân cảnh 2 (8 giây):** [...]
                    - **Phân cảnh 3 (8 giây):** [...]
                    
                    ---SPLIT_SCENE_3---
                    ### 🎬 Kịch bản 3: Góc Flash Sale / Săn Sale sốc
                    - **Kịch bản Lời thoại Voiceover:** [...]
                    - **Phân cảnh 1 (8 giây):** [...]
                    - **Phân cảnh 2 (8 giây):** [...]
                    - **Phân cảnh 3 (8 giây):** [...]
                    """
          contents.append(prompt_text)

          response = model.generate_content(contents)
          full_text = response.text

          # Tách an toàn tuyệt đối dựa vào các thẻ phân tách rõ ràng
          try:
            p_split = full_text.split("---SPLIT_ANALYZE---")
            analyze_part = p_split[1].split("---SPLIT_SCENE_")[0] if len(p_split) > 1 else full_text
            st.session_state.product_analysis = analyze_part

            s_parts = full_text.split("---SPLIT_SCENE_")
            st.session_state.script_1 = s_parts[1] if len(s_parts) > 1 else "Đang cập nhật..."
            st.session_state.script_2 = s_parts[2] if len(s_parts) > 2 else "Đang cập nhật..."
            st.session_state.script_3 = s_parts[3] if len(s_parts) > 3 else "Đang cập nhật..."
          except Exception:
            st.session_state.product_analysis = full_text
            st.session_state.script_1 = full_text
            st.session_state.script_2 = ""
            st.session_state.script_3 = ""

          extracted_name = "Dự án sản phẩm"
          for line in full_text.split("\n"):
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
              st.session_state.product_analysis,
              full_text,
          )
          st.success("✅ Phân tích thành công và đã tự động lưu dự án!")
          st.rerun()
        except Exception as e:
          st.error(f"Lỗi khi gọi API: {e}")

# --- 6. HIỂN THỊ GIAO DIỆN SẠCH SẼ, 2 CỘT PHÂN TÍCH & KỊCH BẢN ---
if st.session_state.product_analysis:
  st.markdown("<br>", unsafe_allow_html=True)
  st.markdown(
      "<h2 style='text-align: center; color: #4F46E5;'>🔍 Phân Tích Chi Tiết"
      " Sản Phẩm</h2>",
      unsafe_allow_html=True,
  )
  st.markdown("<br>", unsafe_allow_html=True)

  analysis_text = st.session_state.product_analysis
  col_left, col_right = st.columns(2)

  mid_idx = len(analysis_text) // 2
  split_idx = analysis_text.find("\n\n", mid_idx)
  if split_idx == -1:
    split_idx = mid_idx

  with col_left:
    st.markdown(
        '<div style="background-color: #F9FAFB; padding: 20px; border-radius:'
        ' 10px; border: 1px solid #E5E7EB;">',
        unsafe_allow_html=True,
    )
    st.markdown(analysis_text[:split_idx])
    st.markdown("</div>", unsafe_allow_html=True)

  with col_right:
    st.markdown(
        '<div style="background-color: #F9FAFB; padding: 20px; border-radius:'
        ' 10px; border: 1px solid #E5E7EB;">',
        unsafe_allow_html=True,
    )
    st.markdown(analysis_text[split_idx:])
    st.markdown("</div>", unsafe_allow_html=True)

  st.markdown("<br><hr><br>", unsafe_allow_html=True)
  st.markdown(
      "<h2 style='text-align: center; color: #4F46E5;'>🎬 Kịch Bản Quảng Cáo &"
      " Xuất Prompt Veo 3</h2>",
      unsafe_allow_html=True,
  )
  st.markdown("<br>", unsafe_allow_html=True)

  # --- HIỂN THỊ KỊCH BẢN 1 ---
  st.markdown(
      '<div style="background-color: #F3F4F6; padding: 25px; border-radius:'
      ' 12px; border: 1px solid #E5E7EB;">',
      unsafe_allow_html=True,
  )
  st.markdown(
      st.session_state.script_1
      if st.session_state.script_1
      else "Đang cập nhật..."
  )
  st.markdown("</div>", unsafe_allow_html=True)
  if st.button(
      "👉 Xuất Prompt Veo 3 cho Kịch bản 1",
      key="btn_v1",
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
            f"Dựa vào Kịch bản 1 sau (có voice và các phân cảnh 8 giây), hãy xuất Prompt Veo 3 đồng bộ tuyệt đối:\n{st.session_state.script_1}"
        )
        st.session_state.veo_prompts = res_v.text
        st.success("✅ Đã xuất Prompt Veo 3 Kịch bản 1 thành công!")
        st.rerun()
      except Exception as e:
        st.error(f"Lỗi: {e}")

  st.markdown("<br>", unsafe_allow_html=True)

  # --- HIỂN THỊ KỊCH BẢN 2 ---
  st.markdown(
      '<div style="background-color: #F3F4F6; padding: 25px; border-radius:'
      ' 12px; border: 1px solid #E5E7EB;">',
      unsafe_allow_html=True,
  )
  st.markdown(
      st.session_state.script_2
      if st.session_state.script_2
      else "Đang cập nhật..."
  )
  st.markdown("</div>", unsafe_allow_html=True)
  if st.button(
      "👉 Xuất Prompt Veo 3 cho Kịch bản 2",
      key="btn_v2",
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
            f"Dựa vào Kịch bản 2 sau (có voice và các phân cảnh 8 giây), hãy xuất Prompt Veo 3 đồng bộ tuyệt đối:\n{st.session_state.script_2}"
        )
        st.session_state.veo_prompts = res_v.text
        st.success("✅ Đã xuất Prompt Veo 3 Kịch bản 2 thành công!")
        st.rerun()
      except Exception as e:
        st.error(f"Lỗi: {e}")

  st.markdown("<br>", unsafe_allow_html=True)

  # --- HIỂN THỊ KỊCH BẢN 3 ---
  st.markdown(
      '<div style="background-color: #F3F4F6; padding: 25px; border-radius:'
      ' 12px; border: 1px solid #E5E7EB;">',
      unsafe_allow_html=True,
  )
  st.markdown(
      st.session_state.script_3
      if st.session_state.script_3
      else "Đang cập nhật..."
  )
  st.markdown("</div>", unsafe_allow_html=True)
  if st.button(
      "👉 Xuất Prompt Veo 3 cho Kịch bản 3",
      key="btn_v3",
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
            f"Dựa vào Kịch bản 3 sau (có voice và các phân cảnh 8 giây), hãy xuất Prompt Veo 3 đồng bộ tuyệt đối:\n{st.session_state.script_3}"
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
      placeholder="Nhập yêu cầu riêng cho các kịch bản gọi thêm...",
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
            f"\n\n🚨 GHI CHÚ RIÊNG: '{extra_user_notes}'."
            if extra_user_notes.strip()
            else ""
        )
        extra_prompt = f"""
                Hãy viết THÊM 3 kịch bản quảng cáo mới hoàn toàn ở 3 góc tiếp cận mới (So sánh chất lượng, Trải nghiệm bất ngờ, Chuyên gia phân tích).
                {extra_note_instruction}
                LƯU Ý: Viết kịch bản voice trước rồi mới chia thành các phân cảnh chuẩn 8 giây. CẤM tuyệt đối dùng từ ngữ livestream và KHÔNG hiển thị câu hook. BẮT BUỘC tiếp tục bám sát và khai thác đúng biến thể Hot đã xác định.
                """
        res_extra = model.generate_content(extra_prompt)
        st.session_state.script_3 += "\n\n" + res_extra.text
        save_project_db(
            st.session_state.current_project_name,
            st.session_state.product_analysis,
            st.session_state.product_analysis
            + "\n---SPLIT_ANALYZE---\n---SPLIT_SCENE_1---\n"
            + st.session_state.script_1
            + "\n---SPLIT_SCENE_2---\n"
            + st.session_state.script_2
            + "\n---SPLIT_SCENE_3---\n"
            + st.session_state.script_3,
        )
        st.success("Đã bổ sung thêm kịch bản mới thành công!")
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
