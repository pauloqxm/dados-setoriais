import os
import io
import json
import re
import pandas as pd
import streamlit as st
from datetime import datetime, date
from typing import Optional, List
import math

# =========================
# Google Sheets connection
# =========================
def get_gspread_client():
    """
    Tenta autenticar com gspread usando, nesta ordem:
    1) st.secrets["gcp_service_account"]
    2) arquivo local "service_account.json"
    3) variável de ambiente GOOGLE_APPLICATION_CREDENTIALS
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except Exception:
        st.error("Bibliotecas do Google não estão instaladas. Adicione 'gspread' e 'google-auth' ao requirements.txt.")
        return None

    creds_info = None

    # 1) st.secrets
    if "gcp_service_account" in st.secrets:
        creds_info = st.secrets["gcp_service_account"]
    else:
        # 2) arquivo local
        sa_path = "service_account.json"
        if os.path.exists(sa_path):
            try:
                with open(sa_path, "r", encoding="utf-8") as f:
                    creds_info = json.load(f)
            except Exception as e:
                st.warning(f"Não consegui ler service_account.json: {e}")
        # 3) variável de ambiente
        if creds_info is None and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            env_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
            if os.path.exists(env_path):
                try:
                    with open(env_path, "r", encoding="utf-8") as f:
                        creds_info = json.load(f)
                except Exception as e:
                    st.warning(f"Não consegui ler credenciais de {env_path}: {e}")

    if not creds_info:
        st.error(
            "As credenciais do Google não foram configuradas.\n"
            "Use st.secrets['gcp_service_account'] **ou** um arquivo local service_account.json "
            "**ou** a variável de ambiente GOOGLE_APPLICATION_CREDENTIALS apontando para o JSON."
        )
        return None

    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = Credentials.from_service_account_info(creds_info, scopes=scope)

    import gspread  # garante disponível aqui também
    client = gspread.authorize(credentials)
    return client


# =========================
# Config da Planilha-Alvo
# =========================
SPREADSHEET_ID = "1tWyQQow2jhP50hSLSc00CvzfWVubpcd48MUeVvWTa_s"
WORKSHEET_NAME = "Página1"

FORM_HEADER = [
    "timestamp",
    "data_nascimento",
    "nome_do_filiado",
    "email_atual",
    "celular_whatsapp_atual",
    "corrigir_telefone_whatsapp",
    "novo_celular_whatsapp",
    "corrigir_email",
    "novo_email",
    "setorial",
]

def clean_value(value):
    """Limpa valores para serem compatíveis com JSON/Sheets"""
    if value is None or pd.isna(value) or str(value).strip() in ['', 'nan', 'NaN']:
        return ""
    elif isinstance(value, (int, float)):
        # Remove .0 de números inteiros
        if value == int(value):
            return str(int(value))
        else:
            return str(value)
    else:
        return str(value).strip()

def salvar_em_planilha(dados_formulario: dict) -> bool:
    """
    Salva os dados do formulário em uma planilha do Google Sheets:
    - Abre por ID (SPREADSHEET_ID).
    - Usa/Cria a aba WORKSHEET_NAME.
    - Garante cabeçalho FORM_HEADER se estiver vazia.
    - Anexa a linha na ordem do FORM_HEADER.
    """
    try:
        client = get_gspread_client()
        if client is None:
            return False

        import gspread
        sh = client.open_by_key(SPREADSHEET_ID)

        # Tenta abrir a aba; se não existir, cria
        try:
            ws = sh.worksheet(WORKSHEET_NAME)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=WORKSHEET_NAME, rows=1000, cols=max(len(FORM_HEADER), 10))

        existing = ws.get_all_values()
        if not existing:
            ws.append_row(FORM_HEADER, value_input_option="USER_ENTERED")

        # Limpa todos os valores antes de enviar
        cleaned_payload = {}
        for key, value in dados_formulario.items():
            cleaned_payload[key] = clean_value(value)
        
        # Remove .0 do final do telefone atual e novo
        for campo in ['celular_whatsapp_atual', 'novo_celular_whatsapp']:
            if campo in cleaned_payload:
                valor = str(cleaned_payload[campo])
                if valor.endswith('.0'):
                    cleaned_payload[campo] = valor[:-2]
                elif '.' in valor and valor.replace('.', '').isdigit():
                    # Se for número decimal, converte para inteiro
                    try:
                        cleaned_payload[campo] = str(int(float(valor)))
                    except:
                        pass

        row = [cleaned_payload.get(k, "") for k in FORM_HEADER]
        ws.append_row(row, value_input_option="USER_ENTERED")
        return True

    except Exception as e:
        st.error(f"Erro ao salvar na planilha: {e}")
        return False


# ============ Configurações iniciais ============
st.set_page_config(page_title="Atualização de Contatos — Filiados", page_icon="🗂️", layout="centered")

# ======== Tema (vermelho) + estilos ========
st.markdown(
    """
    <style>
    :root {
        --pt-red: #C00000;
        --pt-red-dark: #8F0000;
        --pt-red-light: #FF4B4B;
        --pt-red-soft: #FFF5F5;
        --text: #1F2937;
        --muted: #6B7280;
        --card: #ffffff;
        --border: #E5E7EB;
        --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }
    
    .main {
        background: linear-gradient(135deg, #FFF5F5 0%, #FFFFFF 50%, #FFF0F0 100%);
    }
    
    .stApp {
        background: linear-gradient(135deg, #FFF5F5 0%, #FFFFFF 50%, #FFF0F0 100%);
    }
    
    .app-topbar {
        border-radius: 16px;
        overflow: hidden;
        box-shadow: var(--shadow);
        border: 2px solid var(--pt-red-soft);
        margin-bottom: 2rem;
        background: white;
    }
    
    .desc {
        margin-top: .5rem;
        font-weight: 700;
        color: var(--pt-red-dark);
        background: linear-gradient(90deg, var(--pt-red-soft), #ffffff, var(--pt-red-soft));
        text-align: center;
        padding: 12px 20px;
        font-size: 1.1rem;
        border-top: 2px solid var(--pt-red-soft);
    }
    
    .small { font-size: 0.9rem; color: var(--muted); }
    .ok { color: #065f46; }
    .warn { color: #92400e; }
    .err { color: #991b1b; }

    .card {
        border-radius: 16px;
        padding: 20px;
        box-shadow: var(--shadow);
        background: white;
        border: 2px solid var(--pt-red-soft);
        margin: 1rem 0;
    }
    
    .section-title {
        color: var(--pt-red-dark);
        font-weight: 700;
        font-size: 1.4rem;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid var(--pt-red-soft);
    }

    /* Botão principal */
    div.stButton > button {
        background: linear-gradient(135deg, var(--pt-red), var(--pt-red-dark));
        color: #fff;
        border: none;
        border-radius: 12px;
        padding: 12px 24px;
        font-weight: 700;
        font-size: 1.1rem;
        box-shadow: var(--shadow);
        transition: all 0.3s ease;
        width: 100%;
    }
    
    div.stButton > button:hover {
        background: linear-gradient(135deg, var(--pt-red-light), var(--pt-red));
        transform: translateY(-2px);
        box-shadow: 0 8px 15px rgba(192, 0, 0, 0.3);
    }

    /* Inputs */
    .stTextInput input, .stSelectbox select, .stDateInput input {
        border-radius: 12px !important;
        border: 2px solid #f0d3d3 !important;
        padding: 12px !important;
        font-size: 1rem !important;
    }
    
    .stTextInput input:focus, .stSelectbox select:focus, .stDateInput input:focus {
        outline: none !important;
        border-color: var(--pt-red) !important;
        box-shadow: 0 0 0 3px rgba(192, 0, 0, 0.1) !important;
    }
    
    /* Checkbox */
    .stCheckbox label {
        font-weight: 600;
        color: var(--pt-red-dark);
    }
    
    /* Success message */
    .success-box {
        background: linear-gradient(135deg, #F0FFF4, #C6F6D5);
        border: 2px solid #48BB78;
        border-radius: 16px;
        padding: 2rem;
        text-align: center;
        margin: 2rem 0;
        box-shadow: var(--shadow);
    }
    
    .success-icon {
        font-size: 3rem;
        margin-bottom: 1rem;
    }

    /* Divider color trick */
    hr { 
        border-color: #f5caca !important;
        margin: 2rem 0;
        height: 3px;
        background: linear-gradient(90deg, transparent, var(--pt-red-soft), transparent);
        border: none;
    }
    
    /* Labels */
    .stMarkdown h3 {
        color: var(--pt-red-dark) !important;
        font-weight: 700 !important;
    }
    
    .stMarkdown h2 {
        color: var(--pt-red-dark) !important;
        font-weight: 700 !important;
        border-left: 4px solid var(--pt-red);
        padding-left: 1rem;
        margin-top: 2rem;
    }
    
    .stMarkdown h1 {
        color: var(--pt-red-dark) !important;
        text-align: center;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ======= Barra superior (imagem) + descrição =======
with st.container():
    st.markdown('<div class="app-topbar">', unsafe_allow_html=True)
    st.image(
        "https://pt.org.br/wp-content/uploads/2025/09/whatsapp-image-2025-09-09-at-162545.jpeg",
        use_container_width=True,
    )
    st.markdown(
        '<div class="desc">Atualize os seus dados cadastrais e participe das instâncias internas do PT</div>',
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)

st.title("🗂️ Atualização de Contatos de Filiados")
st.caption("Consulte pelo aniversário e, se necessário, envie correções de contato para a planilha oficial.")

# ============ Entrada de dados base ============
@st.cache_data(show_spinner=False)
def load_csv(path_or_buffer) -> pd.DataFrame:
    # Tenta detectar separador automaticamente
    df = pd.read_csv(path_or_buffer, sep=None, engine="python")
    # Normaliza nomes de colunas (sem acentos/caixa e troca espaços por sublinhado)
    def norm(s: str) -> str:
        import unicodedata, re
        s2 = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))
        s2 = s2.lower()
        s2 = re.sub(r'\s+', '_', s2.strip())
        return s2
    df.columns = [norm(c) for c in df.columns]
    return df

# Aceita múltiplos nomes/variações do arquivo
CSV_CANDIDATES = [
    "FILIADOSDADOS.CSV",
    "FILIADOSDADOS.csv",
    "FILADOSDADOS.CSV",
    "FILADOSDADOS.csv",
    "filiaDOSdados.csv",
    "filiaDOSdados.CSV",
]

csv_source = None
for candidate in CSV_CANDIDATES:
    if os.path.exists(candidate):
        csv_source = candidate
        break

if not csv_source:
    up = st.file_uploader("Envie a planilha .csv (separadores automáticos).", type=["csv"])
    if up:
        csv_source = io.BytesIO(up.read())

if not csv_source:
    st.stop()

with st.spinner("Carregando a base..."):
    df = load_csv(csv_source)

# ======== Colunas esperadas + utilitários ========
CANDS_DN = ["data_de_nascimento","data_nascimento","data_nasc","nascimento","dt_nasc","dt_nascimento"]
CANDS_NOME = ["nome_do_filiado","nome","nome_completo"]
CANDS_EMAIL = ["e-mail","email","e_mail"]
CANDS_WHATS = ["celular_whatsapp","celular","telefone","telefone_whatsapp","whatsapp"]

def first_col(df, options: List[str]) -> Optional[str]:
    for c in options:
        if c in df.columns:
            return c
    return None

col_dn = first_col(df, CANDS_DN)
col_nome = first_col(df, CANDS_NOME)
col_email = first_col(df, CANDS_EMAIL)
col_whats = first_col(df, CANDS_WHATS)

missing = [("Data de Nascimento", col_dn), ("Nome", col_nome), ("E-mail", col_email), ("Celular/WhatsApp", col_whats)]
missing_cols = [label for label, val in missing if val is None]
if missing_cols:
    st.error(
        "As seguintes colunas não foram encontradas automaticamente na planilha: "
        + ", ".join([f"**{m}**" for m in missing_cols])
        + ".\n\n"
        "Renomeie as colunas ou ajuste os nomes candidatos no código."
    )
    st.stop()

# Normaliza datas da coluna DN para tipo date
def to_date_safe(v):
    if pd.isna(v):
        return None
    # Tenta vários formatos comuns
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(str(v).strip(), fmt).date()
        except Exception:
            continue
    # Último recurso: pandas to_datetime
    try:
        return pd.to_datetime(v, dayfirst=True).date()
    except Exception:
        return None

# Formatação do telefone: remove ".0" e não dígitos; coloca DDD entre parênteses
def only_digits(s: str) -> str:
    return re.sub(r"\D+", "", s or "")

def format_phone_br(s: str) -> str:
    digits = only_digits(str(s))
    if digits.endswith('.0'):
        digits = digits[:-2]
    if len(digits) < 3:  # sem DDD não formatar
        return digits
    ddd = digits[:2]
    resto = digits[2:]
    if len(resto) == 8:
        resto = f"{resto[:4]}-{resto[4:]}"
    elif len(resto) == 9:
        resto = f"{resto[:5]}-{resto[5:]}"
    return f"({ddd}) {resto}"

df["_dn_date"] = df[col_dn].apply(to_date_safe)

# ============ Formulário de consulta ============
st.markdown('<div class="section-title">🔎 Consulta por data de nascimento</div>', unsafe_allow_html=True)

# Libera datas antigas e evita erro de faixa:
dob = st.date_input(
    "Data de nascimento",
    format="DD/MM/YYYY",
    value=None,
    min_value=date(1900, 1, 1),
    max_value=date.today(),
)
if dob is None:
    st.stop()

# Busca registros desta data
matches = df[df["_dn_date"] == dob].copy()

if matches.empty:
    st.info("Nenhum registro encontrado para esta data. Verifique a data ou a planilha.")
    st.stop()

# Se houver mais de um, permite escolher pelo nome
opcoes = matches[col_nome].fillna("(sem nome)").tolist()
escolha = st.selectbox("Selecione o filiado (se houver homônimos na mesma data):", options=opcoes)
selecionado = matches[matches[col_nome] == escolha].iloc[0]

st.markdown("### 📄 Dados do cadastro")

# Função para formatar os valores e substituir NaN/vazios
def formatar_valor(valor):
    if valor is None or pd.isna(valor) or str(valor).strip() in ['', 'nan', 'NaN']:
        return "Sem informação (atualize)"
    return str(valor).strip()

# Obtém e formata os valores
nome_formatado = formatar_valor(selecionado.get(col_nome, ""))
email_formatado = formatar_valor(selecionado.get(col_email, ""))
telefone_raw = selecionado.get(col_whats, "")
telefone_formatado = formatar_valor(telefone_raw)

# Se não for "Sem informação", formata o telefone
if telefone_formatado != "Sem informação (atualize)":
    telefone_formatado = format_phone_br(telefone_formatado)

# Criando um faux selectbox para exibir os dados
st.markdown(
    f"""
    <div style="
        border: 1px solid #f0d3d3;
        border-radius: 12px;
        padding: 12px;
        background-color: white;
        font-size: 1rem;
        color: #1F2937;
        margin-bottom: 1rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    ">
    <div style="font-weight: 600; color: #6B7280; font-size: 0.9rem; margin-bottom: 8px;">Dados do cadastro atual</div>
    <div style="line-height: 1.5;">
        <strong>Nome:</strong> {nome_formatado}<br>
        <strong>E-mail:</strong> {email_formatado}<br>
        <strong>Celular/WhatsApp:</strong> {telefone_formatado}
    </div>
    </div>
    """, 
    unsafe_allow_html=True
)

st.divider()

# ============ Correções ============
st.markdown('<div class="section-title">✍️ Correções de contato (opcional)</div>', unsafe_allow_html=True)

colA, colB = st.columns(2)
with colA:
    opt_fone = st.checkbox("Corrigir Telefone/WhatsApp")
with colB:
    opt_mail = st.checkbox("Corrigir E-mail")

novo_fone = None
novo_mail = None

if opt_fone:
    novo_fone = st.text_input("Novo Telefone/WhatsApp", placeholder="(XX) 90000-0000")

if opt_mail:
    novo_mail = st.text_input("Novo E-mail", placeholder="exemplo@dominio.com")

# ============ Setorial ============
st.markdown('<div class="section-title">🏷️ Setorial</div>', unsafe_allow_html=True)
setorial = st.selectbox("Selecione um setorial", ["Cultura", "Agrário"])

# ============ Envio para Google Sheets ============
st.divider()
st.markdown('<div class="section-title">📤 Enviar atualização</div>', unsafe_allow_html=True)
st.caption("As respostas serão anexadas à planilha indicada, com cabeçalho na primeira linha se ainda não existir.")

with st.form("envio_form"):
    submitted = st.form_submit_button("Enviar atualização")
    if submitted:
        # Remove .0 do telefone atual e trata NaN
        telefone_atual = clean_value(selecionado.get(col_whats, ""))
        if telefone_atual.endswith('.0'):
            telefone_atual = telefone_atual[:-2]
        
        # Se o usuário digitou novo telefone, salvar somente os dígitos e remover .0
        novo_fone_digits = only_digits(novo_fone) if novo_fone else ""
        if novo_fone_digits.endswith('.0'):
            novo_fone_digits = novo_fone_digits[:-2]

        payload = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_nascimento": dob.strftime("%d/%m/%Y"),
            "nome_do_filiado": clean_value(selecionado.get(col_nome, "")),
            "email_atual": clean_value(selecionado.get(col_email, "")),
            "celular_whatsapp_atual": telefone_atual,
            "corrigir_telefone_whatsapp": "Sim" if opt_fone else "Não",
            "novo_celular_whatsapp": novo_fone_digits,
            "corrigir_email": "Sim" if opt_mail else "Não",
            "novo_email": clean_value(novo_mail or ""),
            "setorial": setorial,
        }

        ok = salvar_em_planilha(payload)
        if ok:
            st.markdown(
                """
                <div class="success-box">
                    <div class="success-icon">✅</div>
                    <h3>Envio realizado com sucesso!</h3>
                </div>
                """, 
                unsafe_allow_html=True
            )
        else:
            st.error("Não foi possível enviar para a planilha. Verifique as credenciais e dependências.")
