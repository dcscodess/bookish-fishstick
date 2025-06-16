import streamlit as st
import hashlib
from sqlalchemy import text
from fpdf import FPDF
from PIL import Image
import pandas as pd
import io, zipfile, os
from datetime import datetime, date

# ---------- MYSQL USER AUTHENTICATION ----------

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, email, password):
    conn = st.connection("mysql", type="sql")
    password_hash = hash_password(password)
    try:
        with conn.session as session:
            session.execute(
                text("INSERT INTO users (username, email, password_hash) VALUES (:username, :email, :password_hash)"),
                {"username": username, "email": email, "password_hash": password_hash}
            )
            session.commit()
        st.success("Registration successful! Please log in.")
    except Exception as e:
        st.error(f"Registration failed: {e}")

def login_user(username, password):
    conn = st.connection("mysql", type="sql")
    password_hash = hash_password(password)
    result = conn.query(
        "SELECT * FROM users WHERE username = :username AND password_hash = :password_hash",
        params={"username": username, "password_hash": password_hash},
        ttl="0"
    )
    return len(result) > 0

def get_user_id(username):
    conn = st.connection("mysql", type="sql")
    result = conn.query("SELECT id FROM users WHERE username = :username", params={"username": username})
    if not result.empty:
        return result.iloc[0]['id']
    else:
        return None

# ---------- STATIC ASSET PATHS ----------

ORG_ASSETS = {
    "DLithe": {
        "logo": "dlithe_logo.png",
        "seal": "dlithe_seal.png",
        "signature": "dlithe_signature.jpg"
    },
    "nxtAlign": {
        "logo": "nxtalign_logo.png",
        "seal": "nxtalign_seal.png",
        "signature": "nxtalign_signature.jpg"
    }
}

# ---------- DOMAIN SHORTFORMS ----------

DOMAIN_SHORTFORMS = {
    "Python Fullstack": "PY",
    "Web Development": "WD",
    "Cybersecurity": "CS",
    "Java Full Stack": "JFSD",
    "AIML": "AIML"
}

# ---------- FLEXIBLE COLUMN MAPPING AND DATE FIX ----------

EXPECTED_COLUMNS = {
    "Name": ["Name", "Full Name", "Student Name"],
    "USN": ["USN", "University Serial Number", "ID"],
    "College": ["College", "Institution", "University"],
    "Email": ["Email", "Email Address", "E-mail"],
    "Phone": ["Phone", "Phone Number", "Contact"],
    "Registered": ["Registered", "Registration Date"],
    "Start Date": ["Start Date", "Internship Start", "Start"],
    "End Date": ["End Date", "Internship End", "End"],
    "Program": ["Program", "Course", "Internship Program"],
    "Mode": ["Mode", "Internship Mode"],
    "Payment Status": ["Payment Status", "Payment", "Paid"],
    "Certificate Issued Date": ["Certificate Issued Date", "Issue Date", "Cert Date"],
    "Intern ID": ["Intern ID", "ID", "Internship ID"],
    "Topic": ["Topic", "Project Topic", "Internship Topic"],
    "Certificate ID": ["Certificate ID", "Cert ID", "Certificate Number"],
    "Domain": ["Domain", "Internship Domain", "Course Domain"]
}

def parse_date_safe(val):
    if val is None or (isinstance(val, float) and pd.isna(val)) or str(val).strip() == "":
        return None
    try:
        dt = pd.to_datetime(val, dayfirst=True, errors='coerce')
        if pd.isna(dt):
            return None
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None

def map_and_clean_columns(df):
    mapped_df = pd.DataFrame()
    for standard_col, aliases in EXPECTED_COLUMNS.items():
        found = None
        for alias in aliases:
            if alias in df.columns:
                found = alias
                break
        if found:
            mapped_df[standard_col] = df[found]
        else:
            mapped_df[standard_col] = None
    mapped_df = mapped_df.where(pd.notnull(mapped_df), None)
    for col in mapped_df.columns:
        mapped_df[col] = mapped_df[col].apply(lambda x: str(x).strip() if isinstance(x, str) else x)
    for date_col in ["Start Date", "End Date", "Certificate Issued Date"]:
        if date_col in mapped_df.columns:
            mapped_df[date_col] = mapped_df[date_col].apply(parse_date_safe)
    return mapped_df

def generate_certificate_id(domain_short, usn, date_obj):
    month_short = date_obj.strftime("%b").upper()
    year_short = date_obj.strftime("%y")
    return f"DL{domain_short}{usn}{month_short}{year_short}"

def clean_text(text):
    if not isinstance(text, str):
        return ""
    return (
        text.replace("’", "'")
            .replace("‘", "'")
            .replace("“", '"')
            .replace("”", '"')
    )

def format_date(dt):
    if isinstance(dt, str):
        try:
            dt = pd.to_datetime(dt).date()
        except Exception:
            return dt
    if isinstance(dt, date) and not isinstance(dt, datetime):
        dt = datetime(dt.year, dt.month, dt.day)
    day = dt.day
    if 4 <= day % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix} {dt:%B %Y}"

def generate_certificate_pdf(
    name, usn, college, start_date_str, end_date_str, topic, cert_id,
    org, logo_path=None, signature_path=None, seal_path=None, cert_type=None
):
    pdf = FPDF(unit='mm', format='A4')
    pdf.set_auto_page_break(False)
    pdf.add_page()
    page_width = pdf.w
    page_height = pdf.h

    border_margin = 8
    border_width = page_width - 2 * border_margin
    border_height = page_height - 2 * border_margin
    pdf.set_line_width(0.5)
    pdf.set_draw_color(0, 0, 0)
    pdf.rect(border_margin, border_margin, border_width, border_height)

    left_margin = border_margin + 8
    right_margin = border_margin + 8
    top_margin = border_margin + 8
    bottom_margin = border_margin + 8
    pdf.set_left_margin(left_margin)
    pdf.set_right_margin(right_margin)

    current_y = top_margin

    # Logo
    if logo_path and os.path.exists(logo_path):
        try:
            logo_width = 35.0
            logo_x = left_margin
            logo_y = current_y
            pdf.image(logo_path, x=logo_x, y=logo_y, w=logo_width)
        except Exception as e:
            st.error(f"Error loading logo image: {e}")

    # Organization header
    if org == "DLithe":
        org_name = "DLithe Consultancy Services Pvt. Ltd."
        org_cin = "CIN: U72900KA2019PTC121035"
        org_footer1 = "Registered office: #51, 1st Main, 6th Block, 3rd Phase, BSK 3rd Stage, Bangalore - 85"
        org_footer2 = "M: 9008815252 | www.dlithe.com | info@dlithe.com"
        for_text = "For DLithe Consultancy Services Pvt. Ltd."
    else:
        org_name = "nxtAlign Innovation Pvt.Ltd."
        org_cin = "CIN: U73100KA2022PTC165879"
        org_footer1 = "Registered office: H No.4061/B 01,Near Chidambar Ashram Health Camp Betageri,Gadag KA 582102"
        org_footer2 = "M: 8553300781 | www.nxtalign.com | nxtalign@gmail.com"
        for_text = "For nxtAlign Innovation Pvt.Ltd."

    pdf.set_xy(left_margin + 40, current_y)
    pdf.set_font("Times", "B", 14)
    pdf.cell(page_width - left_margin - right_margin - 40, 8, org_name, align='R', ln=1)
    pdf.set_font("Times", "", 12)
    pdf.set_x(left_margin + 40)
    pdf.cell(page_width - left_margin - right_margin - 40, 6, org_cin, align='R', ln=1)
    current_y += 18
    pdf.set_y(current_y)
    pdf.ln(8)

    # Certificate ID and Issue Date
    pdf.set_font("Times", "", 12)
    pdf.set_x(left_margin)
    pdf.cell(0, 5, f"Certificate ID: {cert_id}", align='L')
    issued_on_text = f"Issued on: {end_date_str}"
    text_width = pdf.get_string_width(issued_on_text)
    desired_x_position = page_width - right_margin - text_width
    pdf.set_xy(desired_x_position, pdf.get_y())
    pdf.cell(text_width, 5, issued_on_text, align='L')
    pdf.ln(15)

    # --- PROVISIONAL exactly above TO WHOMSOEVER ---
    if cert_type and cert_type.lower() == "provisional":
        pdf.set_font("Times", "B", 16)
        pdf.cell(0, 10, "PROVISIONAL CERTIFICATE", align='C', ln=1)
        pdf.ln(2)  # Small gap

    # Main Heading
    pdf.set_font("Times", "B", 12)
    pdf.cell(0, 5, "TO WHOMSOEVER IT MAY CONCERN", align='C', ln=1)
    pdf.ln(15)

    # Certificate Body (conditional)
    pdf.set_font("Times", "", 12)
    effective_width = page_width - left_margin - right_margin
    pdf.set_x(left_margin)

    if cert_type and cert_type.lower() == "provisional":
        para1 = clean_text(
            f"This is to certify Mr/Ms, {name} bearing USN No: {usn} from {college} "
            f"is currently undergoing a 15-week internship starting from {start_date_str} "
            f"to {end_date_str}, under the mentorship of {org}'s development team. "
            f"{name} is working on {topic}."
        )
    else:
        para1 = clean_text(
            f"This is to certify Mr/Ms, {name} bearing USN No: {usn} from {college} "
            f"has successfully completed a 15-week internship starting from {start_date_str} "
            f"to {end_date_str}, under the mentorship of {org}'s development team. "
            f"{name} has worked on {topic}."
        )

    pdf.multi_cell(effective_width, 6, para1, align='J')
    pdf.ln(6)
    pdf.set_x(left_margin)
    para3 = clean_text("We wish all the best for future endeavours!")
    pdf.multi_cell(effective_width, 6, para3, align='J')

    # --- Move Seal and Signature Higher ---
    content_end_y = pdf.get_y()
    min_sign_y = page_height - bottom_margin - 60  # 20mm higher than before
    y_sign_start = max(content_end_y + 10, min_sign_y)

    pdf.set_font("Times", "", 12)
    pdf.set_xy(page_width - right_margin - pdf.get_string_width(for_text), y_sign_start)
    pdf.cell(pdf.get_string_width(for_text), 7, for_text, align='L')

    # Seal (left)
    if seal_path and os.path.exists(seal_path):
        try:
            seal_width = 30.0
            pdf.image(seal_path, x=left_margin, y=y_sign_start, w=seal_width)
        except Exception as e:
            st.error(f"Error loading seal image: {e}")

    # Signature (right)
    sign_height = 0.0
    sign_y = y_sign_start + 5.0
    sign_width = 40.0
    if signature_path and os.path.exists(signature_path):
        try:
            pdf.image(signature_path, x=page_width - right_margin - sign_width, y=sign_y, w=sign_width)
            try:
                img = Image.open(signature_path)
                w_px, h_px = img.size
                sign_height = (h_px / w_px) * sign_width
            except:
                sign_height = 15.0
        except Exception as e:
            st.error(f"Error loading signature image: {e}")

    # Director label
    director_y = sign_y + sign_height + 5.0
    pdf.set_font("Times", "", 12)
    director_text_width = pdf.get_string_width("Director")
    director_x = page_width - right_margin - sign_width + (sign_width - director_text_width) / 2
    pdf.text(director_x, director_y, "Director")

    # Footer
    pdf.set_font("Times", "", 9)
    footer_y = page_height - bottom_margin - 10
    pdf.set_y(footer_y)
    pdf.set_x(0)
    pdf.cell(0, 5, org_footer1, align='C', ln=1)
    pdf.cell(0, 5, org_footer2, align='C', ln=1)

    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    return pdf_bytes

def insert_certificate_data(user_id, row, org):
    conn = st.connection("mysql", type="sql")
    table = f"certificate_data_{org}"
    with conn.session as session:
        session.execute(
            text(f"""
                INSERT INTO {table} (
                    user_id, name, usn, college, email, phone, registered, start_date, end_date, program, mode, payment_status, certificate_issued_date, intern_id, topic, cert_id, domain, status
                ) VALUES (
                    :user_id, :name, :usn, :college, :email, :phone, :registered, :start_date, :end_date, :program, :mode, :payment_status, :certificate_issued_date, :intern_id, :topic, :cert_id, :domain, 'pending_review'
                )
            """),
            {
                "user_id": user_id,
                "name": row["Name"],
                "usn": row["USN"],
                "college": row["College"],
                "email": row["Email"],
                "phone": row["Phone"],
                "registered": row["Registered"],
                "start_date": row["Start Date"],
                "end_date": row["End Date"],
                "program": row["Program"],
                "mode": row["Mode"],
                "payment_status": row["Payment Status"],
                "certificate_issued_date": row["Certificate Issued Date"],
                "intern_id": row["Intern ID"],
                "topic": row["Topic"],
                "cert_id": row["Certificate ID"],
                "domain": row.get("Domain", "")
            }
        )
        session.commit()

def org_dropdown(label="Organization"):
    return st.selectbox(label, list(ORG_ASSETS.keys()))

def domain_dropdown(label="Domain"):
    return st.selectbox(label, list(DOMAIN_SHORTFORMS.keys()))

def generate_certificates_for_approved(user_id, org, sig_path, seal_path, logo_path):
    conn = st.connection("mysql", type="sql")
    table = f"certificate_data_{org}"
    results = conn.query(
        f"SELECT * FROM {table} WHERE user_id = :user_id AND status = 'Review_Completed'",
        params={"user_id": user_id}
    )

    if results.empty:
        st.warning("No approved certificates to generate.")
        return

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for _, row in results.iterrows():
            name = row["name"]
            usn = row["usn"]
            college = row["college"]
            topic = row["topic"]
            cert_id = row["cert_id"]
            start_date_str = format_date(row["start_date"])
            end_date_str = format_date(row["end_date"])

            pdf_bytes = generate_certificate_pdf(
                name=name,
                usn=usn,
                college=college,
                start_date_str=start_date_str,
                end_date_str=end_date_str,
                topic=topic,
                cert_id=cert_id,
                org=org,
                logo_path=logo_path,
                signature_path=sig_path,
                seal_path=seal_path,
                cert_type="Final"
            )
            pdf_filename = f"{name.replace(' ', '_')}_{cert_id}.pdf"
            zipf.writestr(pdf_filename, pdf_bytes)

    zip_buffer.seek(0)
    st.download_button(
        label="Download Approved Certificates ZIP",
        data=zip_buffer,
        file_name="approved_certificates.zip",
        mime="application/zip"
    )

def main():
    st.title("Internship Certificate Generator")
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        menu = st.sidebar.selectbox("Menu", ["Login", "Register"])
        if menu == "Register":
            st.subheader("Create New Account")
            username = st.text_input("Username", key="reg_user")
            email = st.text_input("Email", key="reg_email")
            password = st.text_input("Password", type="password", key="reg_pass")
            if st.button("Register"):
                register_user(username, email, password)
        elif menu == "Login":
            st.subheader("Login to Your Account")
            username = st.text_input("Username", key="login_user")
            password = st.text_input("Password", type="password", key="login_pass")
            if st.button("Login"):
                if login_user(username, password):
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = username
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
        return

    st.sidebar.success(f"Logged in as {st.session_state['username']}")
    menu = st.sidebar.radio("Actions", ["Upload & Generate Certificates", "Download Approved Certificates", "Logout"])

    if menu == "Logout":
        st.session_state['logged_in'] = False
        st.rerun()
        return

    user_id = get_user_id(st.session_state['username'])

    if menu == "Upload & Generate Certificates":
        st.header("Batch Upload & Certificate Generation")

        cert_type = st.radio("Certificate Type", ["Provisional", "Final"])
        org = org_dropdown()
        domain = domain_dropdown()
        uploaded_file = st.file_uploader("Upload Student Data (CSV)", type="csv")

        if uploaded_file:
            df = pd.read_csv(uploaded_file)
            cleaned_df = map_and_clean_columns(df)
            cleaned_df["Domain"] = domain
            st.write("Mapped Data Preview:", cleaned_df.head())

            generate_clicked = st.button("Generate Certificates")

            if generate_clicked:
                logo_path = ORG_ASSETS[org]["logo"]
                sig_path = ORG_ASSETS[org]["signature"]
                seal_path = ORG_ASSETS[org]["seal"]

                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zipf:
                    for _, row in cleaned_df.iterrows():
                        try:
                            cert_id = generate_certificate_id(
                                DOMAIN_SHORTFORMS[domain],
                                row["USN"],
                                pd.to_datetime(row["End Date"])
                            )
                            pdf_bytes = generate_certificate_pdf(
                                name=row["Name"],
                                usn=row["USN"],
                                college=row["College"],
                                start_date_str=format_date(row["Start Date"]),
                                end_date_str=format_date(row["End Date"]),
                                topic=row["Topic"],
                                cert_id=cert_id,
                                org=org,
                                logo_path=logo_path,
                                signature_path=sig_path,
                                seal_path=seal_path,
                                cert_type=cert_type
                            )
                            pdf_filename = f"{row['Name'].replace(' ', '_')}_{cert_id}.pdf"
                            zipf.writestr(pdf_filename, pdf_bytes)
                            row["Certificate ID"] = cert_id
                            insert_certificate_data(user_id, row, org)
                        except Exception as e:
                            st.error(f"Error generating certificate for {row['Name']}: {str(e)}")

                zip_buffer.seek(0)
                # Program name for ZIP file name
                program_name = cleaned_df["Program"].iloc[0] if "Program" in cleaned_df.columns and not cleaned_df["Program"].isnull().all() else "Certificates"
                now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                zip_filename = f"{program_name}_{now_str}.zip".replace(" ", "_")
                st.session_state['zip_buffer'] = zip_buffer.getvalue()
                st.session_state['zip_filename'] = zip_filename

            if 'zip_buffer' in st.session_state and st.session_state['zip_buffer']:
                st.download_button(
                    label="Download Certificates ZIP",
                    data=st.session_state['zip_buffer'],
                    file_name=st.session_state['zip_filename'],
                    mime="application/zip"
                )

    elif menu == "Download Approved Certificates":
        st.header("Download Approved Certificates")
        org = org_dropdown()
        logo_path = ORG_ASSETS[org]["logo"]
        sig_path = ORG_ASSETS[org]["signature"]
        seal_path = ORG_ASSETS[org]["seal"]
        generate_certificates_for_approved(user_id, org, sig_path, seal_path, logo_path)

if __name__ == "__main__":
    main()
