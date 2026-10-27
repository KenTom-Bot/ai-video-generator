import datetime
import os
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
        .select("id, project_name, created_date, product_info, scripts, status")
        .eq("is_deleted", 0)
        .order("id", desc=True)
        .execute()
    )
    rows = []
    for item in response.data:
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
if "veo_prompts" not in st.session_state:
  st.session_state.veo_prompts = None

# --- 4. THANH ĐIỀU HƯỚNG (SIDEBAR) & LỊCH SỬ DỰ ÁN ---
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
  st.session_state.analysis_col1 = None
  st.session_state.analysis_col2 = None
  st.session_state.script_1 = None
  st.session_state.script_2 = None
  st.session_state.script_3 = None
  st.session_state.veo_prompts = None
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
      if col_p1.button(f"📁 {pname[:22]}...", key=f"load_{pid}"):
        st.session_state.current_project_name = pname
        try:
          c1_split = pscript.split("---SPLIT_COL1_END---")
          st.session_state.analysis_col1 = c1_split[0].replace("---SPLIT_COL1_START---", "").strip()
          
          c2_split = c1_split[1].split("---SPLIT_SCENE_")
          st.session_state.analysis_col2 = c2_split[0].replace("---SPLIT_COL2_START---", "").replace("---SPLIT_COL2_END---", "").strip()
          
          st.session_state.script_1 = c2_split[1].replace("---", "").strip() if len(c2_split) > 1 else ""
          st.session_state.script_2 = c2_split[2].replace("---", "").strip() if len(c2_split) > 2 else ""
          st.session_state.script_3 = c2_split[3].replace("---", "").strip() if len(c2_split) > 3 else ""
        except Exception:
          st.session_state.analysis_col1 = pinfo
          st.session_state.analysis_col2 = ""
          st.session_state.script_1 = pscript
        st.rerun()
      if col_p2.button("❌", key=f"del_{pid}"):
        soft_delete_project(pid)
        st.rerun()  # Tự động làm mới trang ngay khi xóa để cập nhật lại danh sách

st.sidebar.markdown("<br><br><br>", unsafe_allow_html=True)
st.sidebar.divider()
if st.sidebar.button("🚪 Đăng xuất", use_container_width=True):
  st.session_state["password_correct"] = False
  st.rerun()

# --- 5. GIAO DIỆN CHÍNH ---
st.markdown(
    "<h1 style='text-align: center; color: #1F2937;'>🎬 AI Video Viral</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align: center; color: #4B5563; font-size: 16px;'>Hệ thống"
    " tự động hóa 100% ngành hàng: Quét tự động biến thể Hot 🔥, giọng đọc"
    " Hà Nội chuẩn và sinh Prompt Veo 3 chuyên nghiệp.</p>",
    unsafe_allow_html=True,
)
st.divider()

if not st.session_state.analysis_col1:
  st.markdown("### 📦 Thông Tin Đầu Vào Sản Phẩm")
  product_images = st.file_uploader(
      "Tải lên ảnh chụp màn hình sản phẩm có gắn nhãn/icon Hot (hoặc nhiều ảnh mẫu)",
      type=["jpg", "png", "jpeg"],
      accept_multiple_files=True,
      help="Tải ảnh lên để AI tự động phát hiện biến thể gắn nhãn Hot bán chạy nhất.",
  )

  if product_images:
    with st.expander(
        f"👁️ Xem lại danh sách ảnh đã tải lên ({len(product_images)} ảnh)"
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
          "Nhập yêu cầu riêng nếu muốn đổi màu khác (Nếu để trống, AI tự động"
          " chọn biến thể có icon Hot 🔥 làm chủ lực)"
      ),
  )

  st.markdown("<br>", unsafe_allow_html=True)
  col_b1, col_b2, col_b3 = st.columns([1, 2, 1])
  with col_b2:
    analyze_btn = st.button(
        "🚀 Phân Tích & Tạo Kịch Bản Theo Biến Thẻ Hot",
        type="primary",
        use_container_width=True,
    )

  if analyze_btn:
    if not product_images:
      st.error("⚠️ Vui lòng tải lên ít nhất một ảnh sản phẩm!")
    else:
      with st.spinner(
          "🤖 AI đang quét icon Hot 🔥 trên ảnh, khóa biến thể bán chạy và viết kịch bản..."
      ):
        try:
          if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
          else:
            genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

          model = genai.GenerativeModel("gemini-3.8-flash")
          contents = [compress_image_for_ai(img) for img in product_images]

          notes_instruction = (
              f"\n\n🚨 GHI CHÚ RIÊNG CỦA NGƯỜI DÙNG: '{user_notes}'."
              if user_notes.strip()
              else ""
          )

          prompt_text = f"""
                    Bạn là Giám đốc Sản xuất Video Quảng cáo AI chuyên nghiệp cho video ngắn dựng sẵn (Reels, TikTok - KHÔNG LIVESTREAM). 
                    Hãy phân tích kỹ các hình ảnh sản phẩm được tải lên.
                    {notes_instruction}
                    
                    QUY TẮC BẮT BUỘC VỀ BIẾN THỂ BÁN CHẠY (HERO VARIANT):
                    - Bạn PHẢI quét kỹ các hình ảnh giao diện được tải lên để tìm các nhãn, biểu tượng thể hiện sản phẩm bán chạy (như icon ngọn lửa 🔥, chữ "Hot", lượt mua cao). 
                    - BIẾN THỂ NÀO CÓ ICON 🔥 HOẶC NHÃN HOT (Ví dụ: Đầm ĐEN-34D có icon Hot trong ảnh) PHẢI ĐƯỢC TỰ ĐỘNG XÁC ĐỊNH LÀ BIẾN THỂ CHỦ LỰC (HERO VARIANT)[cite: 13].
                    - Toàn bộ nội dung phân tích và 3 kịch bản quảng cáo phía dưới BẮT BUỘC phải lấy biến thể mang nhãn Hot 🔥 đó làm tâm điểm xuyên suốt.
                    
                    QUY TẮC CẤM TUYỆT ĐỐI VỀ VIDEO & HÌNH ẢNH:
                    - CẤM dùng từ ngữ livestream ("mọi người ơi", "giỏ hàng phiên live", "giảm theo suất", "vào giỏ hàng").
                    - CẤM hiển thị phần 3 câu hook giữ chân người xem.
                    - **TUYỆT ĐỐI KHÔNG TEXT, KHÔNG LOGO, KHÔNG NHẠC NỀN** trong mô tả phân cảnh hoặc khi tạo ảnh/video (chỉ cho phép âm thanh hiệu ứng sound effects).
                    
                    QUY TRÌNH SÁNG TẠO KỊCH BẢN CHUẨN:
                    1. Viết kịch bản LỜI THOẠI (Voiceover) tổng thể trước với nhịp đọc nhanh dồn dập, đủ dài cho toàn bộ video (90 - 120 từ tương đương 3 phân cảnh).
                    2. Dựa trực tiếp vào lời thoại đó để chia ra chính xác 3 PHÂN CẢNH, mỗi phân cảnh chuẩn **8 giây**.
                    3. Trong mỗi phân cảnh, cấu trúc bắt buộc phải: **Hình ảnh mô tả (Ở TRÊN)** và **Lời thoại chi tiết của phân cảnh đó (Ở DƯỚI)**.
                    
                    Dòng đầu tiên PHẢI ghi chính xác tên sản phẩm (Ví dụ: Tên sản phẩm: Đầm body...).
                    
                    TRẢ VỀ KẾT QUẢ ĐÚNG THEO CẤU TRÚC PHÂN TÁCH SAU:
                    ---SPLIT_COL1_START---
                    ### 📌 Cột Trái: Chân dung & Hero Variant Hot 🔥
                    - **1. Chân dung Khách hàng & Đặc tính:** ...
                    - **2. KOC Chuẩn Việt, Stylist & Khóa Màu (Hero Variant Hot 🔥):** ...
                    ---SPLIT_COL1_END---

                    ---SPLIT_COL2_START---
                    ### 🎨 Cột Phải: Giải phẫu & Bối cảnh
                    - **3. Giải phẫu Sản phẩm & Khóa Hình học 3D:** ...
                    - **4. Chuẩn Bối Cảnh & Mức Giá:** ...
                    ---SPLIT_COL2_END---
                    
                    ---SPLIT_SCENE_1---
                    ### 🎬 Kịch bản 1: Góc Review Thực Tế / Xưởng tận gốc (Tập trung biến thể Hot)
                    - **Kịch bản Lời thoại Voiceover Tổng thể (90-120 từ, nhịp đọc nhanh Hà Nội):** [...]
                    - **Phân cảnh 1 (8 giây):**
                      - *Hình ảnh:* [Mô tả chi tiết góc máy, hoàn toàn KHÔNG TEXT, KHÔNG LOGO]
                      - *Lời thoại phân cảnh:* [Lời thoại tương ứng]
                    - **Phân cảnh 2 (8 giây):**
                      - *Hình ảnh:* [Mô tả chi tiết góc máy, hoàn toàn KHÔNG TEXT, KHÔNG LOGO]
                      - *Lời thoại phân cảnh:* [Lời thoại tương ứng]
                    - **Phân cảnh 3 (8 giây):**
                      - *Hình ảnh:* [Mô tả chi tiết góc máy, hoàn toàn KHÔNG TEXT, KHÔNG LOGO]
                      - *Lời thoại phân cảnh:* [Lời thoại tương ứng]
                    
                    ---SPLIT_SCENE_2---
                    ### 🎬 Kịch bản 2: Góc Nỗi đau & Tình huống kịch tính (Tập trung biến thể Hot)
                    - **Kịch bản Lời thoại Voiceover Tổng thể (90-120 từ, nhịp đọc nhanh Hà Nội):** [...]
                    - **Phân cảnh 1 (8 giây):**
                      - *Hình ảnh:* [Mô tả chi tiết, hoàn toàn KHÔNG TEXT, KHÔNG LOGO]
                      - *Lời thoại phân cảnh:* [...]
                    - **Phân cảnh 2 (8 giây):**
                      - *Hình ảnh:* [Mô tả chi tiết, hoàn toàn KHÔNG TEXT, KHÔNG LOGO]
                      - *Lời thoại phân cảnh:* [...]
                    - **Phân cảnh 3 (8 giây):**
                      - *Hình ảnh:* [Mô tả chi tiết, hoàn toàn KHÔNG TEXT, KHÔNG LOGO]
                      - *Lời thoại phân cảnh:* [...]
                    
                    ---SPLIT_SCENE_3---
                    ### 🎬 Kịch bản 3: Góc Flash Sale / Săn Sale sốc (Tập trung biến thể Hot)
                    - **Kịch bản Lời thoại Voiceover Tổng thể (90-120 từ, nhịp đọc nhanh Hà Nội):** [...]
                    - **Phân cảnh 1 (8 giây):**
                      - *Hình ảnh:* [Mô tả chi tiết, hoàn toàn KHÔNG TEXT, KHÔNG LOGO]
                      - *Lời thoại phân cảnh:* [...]
                    - **Phân cảnh 2 (8 giây):**
                      - *Hình ảnh:* [Mô tả chi tiết, hoàn toàn KHÔNG TEXT, KHÔNG LOGO]
                      - *Lời thoại phân cảnh:* [...]
                    - **Phân cảnh 3 (8 giây):**
                      - *Hình ảnh:* [Mô tả chi tiết, hoàn toàn KHÔNG TEXT, KHÔNG LOGO]
                      - *Lời thoại phân cảnh:* [...]
                    """
          contents.append(prompt_text)

          response = model.generate_content(contents)
          full_text = response.text

          try:
            c1_split = full_text.split("---SPLIT_COL1_END---")
            st.session_state.analysis_col1 = c1_split[0].replace("---SPLIT_COL1_START---", "").strip()

            c2_split = c1_split[1].split("---SPLIT_SCENE_")
            st.session_state.analysis_col2 = c2_split[0].replace("---SPLIT_COL2_START---", "").replace("---SPLIT_COL2_END---", "").strip()

            st.session_state.script_1 = c2_split[1].replace("---", "").strip() if len(c2_split) > 1 else ""
            st.session_state.script_2 = c2_split[2].replace("---", "").strip() if len(c2_split) > 2 else ""
            st.session_state.script_3 = c2_split[3].replace("---", "").strip() if len(c2_split) > 3 else ""
          except Exception:
            st.session_state.analysis_col1 = full_text
            st.session_state.analysis_col2 = ""
            st.session_state.script_1 = full_text

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
              st.session_state.analysis_col1 + "\n---SPLIT_COL1_END---\n" + st.session_state.analysis_col2,
              full_text,
          )
          st.success("✅ Phân tích thành công theo biến thể Hot 🔥 và đã lưu lên Supabase!")
          st.rerun()
        except Exception as e:
          st.error(f"Lỗi khi gọi API: {e}")

# --- 6. HIỂN THỊ GIAO DIỆN CHIA 2 CỘT SẠCH SẼ, KHÔNG KHUNG THỪA ---
if st.session_state.analysis_col1:
  st.markdown("<br>", unsafe_allow_html=True)
  st.markdown(
      "<h2 style='text-align: center; color: #4F46E5;'>🔍 Phân Tích Biến Thể Hot"
      " & Chi Tiết Sản Phẩm</h2>",
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
      "<h2 style='text-align: center; color: #4F46E5;'>🎬 Kịch Bản Quảng Cáo &"
      " Xuất Prompt Veo 3</h2>",
      unsafe_allow_html=True,
  )
  st.markdown("<br>", unsafe_allow_html=True)

  # --- KỊCH BẢN 1 ---
  st.markdown(st.session_state.script_1)
  if st.button(
      "👉 Xuất Prompt Veo 3 cho Kịch bản 1 (Biến thể Hot 🔥 - Không Text, Không Logo)",
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
            f"Dựa vào Kịch bản 1 sau, hãy xuất Prompt Veo 3 đồng bộ tuyệt đối với biến thể Hot (Nghiêm ngặt: Không text, không logo, không nhạc nền, chỉ có âm thanh hiệu ứng):\n{st.session_state.script_1}"
        )
        st.session_state.veo_prompts = res_v.text
        st.success("✅ Đã xuất Prompt Veo 3 Kịch bản 1 thành công!")
        st.rerun()
      except Exception as e:
        st.error(f"Lỗi: {e}")

  st.markdown("<br>", unsafe_allow_html=True)
  st.markdown("---")

  # --- KỊCH BẢN 2 ---
  st.markdown(st.session_state.script_2)
  if st.button(
      "👉 Xuất Prompt Veo 3 cho Kịch bản 2 (Biến thể Hot 🔥 - Không Text, Không Logo)",
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
            f"Dựa vào Kịch bản 2 sau, hãy xuất Prompt Veo 3 đồng bộ tuyệt đối với biến thể Hot (Nghiêm ngặt: Không text, không logo, không nhạc nền, chỉ có âm thanh hiệu ứng):\n{st.session_state.script_2}"
        )
        st.session_state.veo_prompts = res_v.text
        st.success("✅ Đã xuất Prompt Veo 3 Kịch bản 2 thành công!")
        st.rerun()
      except Exception as e:
        st.error(f"Lỗi: {e}")

  st.markdown("<br>", unsafe_allow_html=True)
  st.markdown("---")

  # --- KỊCH BẢN 3 ---
  st.markdown(st.session_state.script_3)
  if st.button(
      "👉 Xuất Prompt Veo 3 cho Kịch bản 3 (Biến thể Hot 🔥 - Không Text, Không Logo)",
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
            f"Dựa vào Kịch bản 3 sau, hãy xuất Prompt Veo 3 đồng bộ tuyệt đối với biến thể Hot (Nghiêm ngặt: Không text, không logo, không nhạc nền, chỉ có âm thanh hiệu ứng):\n{st.session_state.script_3}"
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
                Hãy viết THÊM 3 kịch bản quảng cáo mới hoàn toàn ở 3 góc tiếp cận mới.
                {extra_note_instruction}
                LƯU Ý NGHIÊM NGẶT: Bắt buộc khai thác biến thể mang nhãn Hot 🔥 làm trọng tâm. Hoàn toàn KHÔNG TEXT, KHÔNG LOGO, KHÔNG NHẠC NỀN. Viết kịch bản voice tổng thể trước rồi chia thành các phân cảnh chuẩn 8 giây (hình ảnh ở trên, lời thoại ở dưới).
                """
        res_extra = model.generate_content(extra_prompt)
        st.session_state.script_3 += "\n\n" + res_extra.text
        save_project_db(
            st.session_state.current_project_name,
            st.session_state.analysis_col1 + "\n---SPLIT_COL1_END---\n" + st.session_state.analysis_col2,
            st.session_state.analysis_col1
            + "\n---SPLIT_COL1_END---\n"
            + st.session_state.analysis_col2
            + "\n---SPLIT_SCENE_1---\n"
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

# --- 7. HIỂN THỊ KẾT QUẢ PROMPT VEO 3 ---
if st.session_state.veo_prompts:
  st.markdown("<br>", unsafe_allow_html=True)
  st.markdown(
      "<h3 style='text-align: center; color: #10B981;'>🎯 Bộ Prompt Veo 3 Hoàn"
      " Chỉnh (Không Text, Không Logo)</h3>",
      unsafe_allow_html=True,
  )
  st.markdown(
      "Sao chép các Prompt dưới đây dán trực tiếp vào Veo 3 để tạo video:"
  )
  st.code(st.session_state.veo_prompts, language="text")
