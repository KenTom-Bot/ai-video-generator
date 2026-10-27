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


# --- HÀM LỌC SẠCH KÝ TỰ RÁC ---
def clean_script_text(raw_text):
  if not raw_text:
    return "Đang cập nhật..."
  cleaned = raw_text.lstrip("1234567890-")
  return cleaned.strip()


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
          
          st.session_state.script_1 = clean_script_text(c2_split[1]) if len(c2_split) > 1 else ""
          st.session_state.script_2 = clean_script_text(c2_split[2]) if len(c2_split) > 2 else ""
          st.session_state.script_3 = clean_script_text(c2_split[3]) if len(c2_split) > 3 else ""
        except Exception:
          st.session_state.analysis_col1 = pinfo
          st.session_state.analysis_col2 = ""
          st.session_state.script_1 = clean_script_text(pscript)
        st.rerun()
      if col_p2.button("❌", key=f"del_{pid}"):
        soft_delete_project(pid)
        st.rerun()

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
    " Hà Nội chuẩn (35-40 chữ/cảnh 8s) và sinh Prompt Ảnh & Video chuyên nghiệp.</p>",
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
        "🚀 Phân Tích & Tạo Kịch Bản Theo Biến Thể Hot",
        type="primary",
        use_container_width=True,
    )

  if analyze_btn:
    if not product_images:
      st.error("⚠️ Vui lòng tải lên ít nhất một ảnh sản phẩm!")
    else:
      with st.spinner(
          "🤖 AI đang quét icon Hot 🔥 trên ảnh, khóa biến thể bán chạy và viết kịch bản chuẩn nhịp 8s..."
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
                    
                    QUY TRÌNH SÁNG TẠO KỊCH BẢN CHUẨN (CỰC KỲ QUAN TRỌNG):
                    1. Mỗi phân cảnh video có thời lượng cố định chuẩn **8 giây**.
                    2. **Giới hạn tuyệt đối từ vựng:** Mỗi phân cảnh 8 giây **chỉ chứa từ 35 đến tối đa 40 chữ** trong phần lời thoại để KOC đọc thong thả, tự nhiên, rõ ràng không bị vấp/quá nhanh.
                    3. **Linh hoạt số lượng phân cảnh:** Nếu nội dung dài, hãy **tự động chia thành nhiều phân cảnh hơn (từ 4 đến 5 phân cảnh)** thay vì ép buộc gò bó trong 3 phân cảnh.
                    4. Trong mỗi phân cảnh, cấu trúc bắt buộc phải: **Hình ảnh mô tả (Ở TRÊN)** và **Lời thoại chi tiết của phân cảnh đó (Ở DƯỚI)**.
                    
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
                    - **Phân cảnh 1 (8 giây - 35-40 chữ):**
                      - *Hình ảnh:* [Mô tả chi tiết góc máy, hoàn toàn KHÔNG TEXT, KHÔNG LOGO]
                      - *Lời thoại phân cảnh (Nhân vật đang nói):* [Lời thoại chuẩn 35-40 chữ]
                    - **Phân cảnh 2 (8 giây - 35-40 chữ):**
                      - *Hình ảnh:* [Mô tả chi tiết góc máy, hoàn toàn KHÔNG TEXT, KHÔNG LOGO]
                      - *Lời thoại phân cảnh (Nhân vật đang nói):* [Lời thoại chuẩn 35-40 chữ]
                    - **Phân cảnh 3 (8 giây - 35-40 chữ):**
                      - *Hình ảnh:* [Mô tả chi tiết góc máy, hoàn toàn KHÔNG TEXT, KHÔNG LOGO]
                      - *Lời thoại phân cảnh (Nhân vật đang nói):* [Lời thoại chuẩn 35-40 chữ]
                    - **Phân cảnh 4 (8 giây - 35-40 chữ - Nếu cần thiết):**
                      - *Hình ảnh:* [...]
                      - *Lời thoại phân cảnh (Nhân vật đang nói):* [...]
                    
                    ---SPLIT_SCENE_2---
                    ### 🎬 Kịch bản 2: Góc Nỗi đau & Tình huống kịch tính (Tập trung biến thể Hot)
                    - **Phân cảnh 1 (8 giây - 35-40 chữ):**
                      - *Hình ảnh:* [...]
                      - *Lời thoại phân cảnh (Nhân vật đang nói):* [...]
                    - **Phân cảnh 2 (8 giây - 35-40 chữ):**
                      - *Hình ảnh:* [...]
                      - *Lời thoại phân cảnh (Nhân vật đang nói):* [...]
                    - **Phân cảnh 3 (8 giây - 35-40 chữ):**
                      - *Hình ảnh:* [...]
                      - *Lời thoại phân cảnh (Nhân vật đang nói):* [...]
                    
                    ---SPLIT_SCENE_3---
                    ### 🎬 Kịch bản 3: Góc Flash Sale / Săn Sale sốc (Tập trung biến thể Hot)
                    - **Phân cảnh 1 (8 giây - 35-40 chữ):**
                      - *Hình ảnh:* [...]
                      - *Lời thoại phân cảnh (Nhân vật đang nói):* [...]
                    - **Phân cảnh 2 (8 giây - 35-40 chữ):**
                      - *Hình ảnh:* [...]
                      - *Lời thoại phân cảnh (Nhân vật đang nói):* [...]
                    - **Phân cảnh 3 (8 giây - 35-40 chữ):**
                      - *Hình ảnh:* [...]
                      - *Lời thoại phân cảnh (Nhân vật đang nói):* [...]
                    """
          contents.append(prompt_text)

          response = model.generate_content(contents)
          full_text = response.text

          try:
            c1_split = full_text.split("---SPLIT_COL1_END---")
            st.session_state.analysis_col1 = c1_split[0].replace("---SPLIT_COL1_START---", "").strip()

            c2_split = c1_split[1].split("---SPLIT_SCENE_")
            st.session_state.analysis_col2 = c2_split[0].replace("---SPLIT_COL2_START---", "").replace("---SPLIT_COL2_END---", "").strip()

            st.session_state.script_1 = clean_script_text(c2_split[1]) if len(c2_split) > 1 else ""
            st.session_state.script_2 = clean_script_text(c2_split[2]) if len(c2_split) > 2 else ""
            st.session_state.script_3 = clean_script_text(c2_split[3]) if len(c2_split) > 3 else ""
          except Exception:
            st.session_state.analysis_col1 = full_text
            st.session_state.analysis_col2 = ""
            st.session_state.script_1 = clean_script_text(full_text)

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
      " Xuất Prompt Ảnh & Video</h2>",
      unsafe_allow_html=True,
  )
  st.markdown("<br>", unsafe_allow_html=True)

  # --- HÀM XỬ LÝ HIỂN THỊ KỊCH BẢN VÀ PROMPT 2 CỘT GỌN GÀNG (TÍCH HỢP KHẨU HÌNH THOẠI) ---
  def handle_script_section(script_title, script_content, state_key):
    st.markdown(script_content)
    
    if st.button(f"👉 Tạo Prompt Ảnh & Video cho {script_title}", key=f"btn_{state_key}", type="primary", use_container_width=True):
      with st.spinner(f"🤖 Đang tạo Prompt chuẩn Ảnh & Video (Kèm khẩu hình thoại nhân vật) cho {script_title}..."):
        try:
          if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
          else:
            genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
          model = genai.GenerativeModel("gemini-3.8-flash")
          res = model.generate_content(
              f"Dựa vào kịch bản sau, hãy xuất ra Prompt chuẩn bằng tiếng Anh cho từng phân cảnh:\n"
              f"1. Prompt Ảnh tĩnh (Midjourney/Flux) (Nghiêm ngặt: không text, không logo).\n"
              f"2. Prompt Video (Veo 3 Pro) (Nghiêm ngặt: không text, không logo, không nhạc nền; ĐẶC BIỆT: Mô tả nhân vật đang cất lời thoại với khẩu hình miệng mấp máy khớp nội dung lời thoại của phân cảnh).\n"
              f"Hãy trả về kết quả tuân thủ đúng định dạng cho từng cảnh xuất hiện trong kịch bản:\n"
              f"### CẢNH 1\n"
              f"IMG_PROMPT: [Nội dung prompt ảnh cảnh 1]\n"
              f"VID_PROMPT: [Nội dung prompt video cảnh 1 kèm khẩu hình thoại]\n\n"
              f"### CẢNH 2\n"
              f"IMG_PROMPT: [Nội dung prompt ảnh cảnh 2]\n"
              f"VID_PROMPT: [Nội dung prompt video cảnh 2 kèm khẩu hình thoại]\n\n"
              f"### CẢNH 3\n"
              f"IMG_PROMPT: [Nội dung prompt ảnh cảnh 3]\n"
              f"VID_PROMPT: [Nội dung prompt video cảnh 3 kèm khẩu hình thoại]\n\n{script_content}"
          )
          st.session_state[state_key] = res.text
          st.success(f"✅ Đã tạo xong Prompt tích hợp thoại cho {script_title}!")
          st.rerun()
        except Exception as e:
          st.error(f"Lỗi: {e}")

    # Nếu đã có prompt, hiển thị giao diện 2 cột đối xứng cho từng cảnh gọn gàng
    p_text = st.session_state.get(state_key)
    if p_text:
      st.markdown(f"<br><h4>🎯 Bộ Prompt Tinh Gọn (Kèm Khẩu Hình Thoại) Cho {script_title}</h4>", unsafe_allow_html=True)
      
      scenes = p_text.split("### CẢNH")
      for sc in scenes[1:]:
        lines = sc.strip().split("\n")
        c_num = lines[0].strip()
        
        img_p = ""
        vid_p = ""
        for l in lines:
          if l.startswith("IMG_PROMPT:"):
            img_p = l.replace("IMG_PROMPT:", "").strip()
          elif l.startswith("VID_PROMPT:"):
            vid_p = l.replace("VID_PROMPT:", "").strip()

        st.markdown(f"**📍 Phân cảnh {c_num}**")
        p_col1, p_col2 = st.columns(2)
        
        with p_col1:
          st.markdown("📷 **Prompt Ảnh Tĩnh (Midjourney / Flux):**")
          st.code(img_p if img_p else sc, language="text")

        with p_col2:
          st.markdown("🎥 **Prompt Video (Veo 3 Pro - Kèm Khẩu Hình Thoại):**")
          st.code(vid_p if vid_p else "Đang cập nhật...", language="text")
        
        st.markdown("---")

  # --- KỊCH BẢN 1 ---
  handle_script_section("Kịch bản 1", st.session_state.script_1, "prompts_s1")
  st.markdown("<br><hr><br>", unsafe_allow_html=True)

  # --- KỊCH BẢN 2 ---
  handle_script_section("Kịch bản 2", st.session_state.script_2, "prompts_s2")
  st.markdown("<br><hr><br>", unsafe_allow_html=True)

  # --- KỊCH BẢN 3 ---
  handle_script_section("Kịch bản 3", st.session_state.script_3, "prompts_s3")

  st.markdown("<br>", unsafe_allow_html=True)
  st.markdown("---")

  st.markdown("#### ➕ Tạo Thêm Kịch Bản Mới (Góc Tiếp Cận Khác)")
  extra_user_notes = st.text_area(
      "📝 Ghi chú / Yêu cầu riêng cho lần gọi thêm này (Tùy chọn)",
      placeholder="Nhập yêu cầu riêng cho các kịch bản gọi thêm...",
      key="extra_notes_input",
  )

  if st.button(
      "🚀 Gọi thêm 3 Kịch bản mới theo yêu cầu", type="primary", use_container_width=True
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
                LƯU Ý NGHIÊM NGẶT: Bắt buộc khai thác biến thể mang nhãn Hot 🔥 làm trọng tâm. Mỗi phân cảnh 8 giây chỉ chứa 35-40 chữ. Hoàn toàn KHÔNG TEXT, KHÔNG LOGO, KHÔNG NHẠC NỀN.
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
