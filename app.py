import os
import io
import json
import re
import pandas as pd
import streamlit as st
from datetime import datetime, date
from typing import Optional, List

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
    client = gspread.authorize(credentials)
    return client

# ============ Configurações iniciais ============
st.set_page_config(page_title="Atualização de Contatos — Filiados", page_icon="🗂️", layout="centered")

# ======== Tema (vermelho) + estilos ========
st.markdown(
    """
    <style>
    :root {
        --pt-red: #C00000;
        --pt-red-dark: #8F0000;
        --pt-red-soft: #FDE8E8;
        --text: #1F2937;
        --muted: #6B7280;
        --card: #ffffff;
        --border: #f1f1f1;
    }
    .app-topbar {
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 8px 24px rgba(0,0,0,.08);
        border: 1px solid var(--border);
    }
    .desc {
        margin-top: .5rem;
        font-weight: 600;
        color: var(--pt-red-dark);
        background: linear-gradient(180deg, #fff, #fff 55%, #fff0 100%);
        text-align: center;
        padding: 8px 10px;
    }
    .small { font-size: 0.9rem; color: var(--muted); }
    .ok { color: #065f46; }
    .warn { color: #92400e; }
    .err { color: #991b1b; }

    .card {
        border-radius: 14px;
        padding: 14px 16px;
        box-shadow: 0 6px 16px rgba(0,0,0,.06);
        background: var(--card);
        border: 1px solid var(--border);
    }

    /* Botão principal */
    div.stButton > button {
        background: linear-gradient(135deg, var(--pt-red), var(--pt-red-dark));
        color: #fff;
        border: none;
        border-radius: 12px;
        padding: 10px 16px;
        font-weight: 700;
        box-shadow: 0 4px 12px rgba(192,0,0,.25);
    }
    div.stButton > button:hover {
        filter: brightness(1.05);
        transform: translateY(-1px);
    }

    /* Inputs */
    .stTextInput input, .stSelectbox, .stDateInput input {
        border-radius: 10px !important;
        border-color: #f0d3d3 !important;
    }
    .stTextInput input:focus, .stDateInput input:focus {
        outline: 2px solid var(--pt-red) !important;
        border-color: var(--pt-red) !important;
    }

    /* Divider color trick */
    hr { border-color: #f5caca !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ======= Barra superior (imagem) + descrição =======
with st.container():
    st.markdown('<div class="app-topbar">', unsafe_allow_html=True)
    st.image(
        "https://pt.org.br/wp-content/uploads/2025/09/whatsapp-image-2025-09-09-at-162545.jpeg",
        use_column_width=True,
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
        # (Mensagem de "Arquivo base encontrado" removida a pedido)
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
    if len(digits) < 3:  # sem DDD não formatar
        return digits
    ddd = digits[:2]
    resto = digits[2:]
    return f"({ddd}) {resto}"

df["_dn_date"] = df[col_dn].apply(to_date_safe)

# ============ Formulário de consulta ============
st.subheader("🔎 Consulta por data de nascimento")

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
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.write("**Nome do filiado:**", selecionado.get(col_nome, ""))
    st.write("**E-mail:**", selecionado.get(col_email, ""))
    # Aplica a formatação no display do telefone/WhatsApp
    raw_phone = selecionado.get(col_whats, "")
    st.write("**Celular/WhatsApp:**", format_phone_br(str(raw_phone)))
    st.markdown('</div>', unsafe_allow_html=True)

st.divider()

# ============ Correções ============
st.subheader("✍️ Correções de contato (opcional)")

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
st.subheader("🏷️ Setorial")
setorial = st.selectbox("Selecione um setorial", ["Cultura", "Agrário"])

# ============ Envio para Google Sheets ============
st.divider()
st.markdown("### 📤 Enviar atualização")
st.caption("As respostas serão anexadas à planilha indicada, com cabeçalho na primeira linha se ainda não existir.")

# URL pré-configurada (pode ser alterada dentro de um expander avançado)
SHEET_URL_DEFAULT = "https://docs.google.com/spreadsheets/d/1tWyQQow2jhP50hSLSc00CvzfWVubpcd48MUeVvWTa_s/edit?gid=0"
sheet_url = SHEET_URL_DEFAULT

with st.expander("Opções avançadas (alterar planilha de destino)"):
    sheet_url = st.text_input(
        "URL da Planilha Google (aba onde deseja registrar as respostas):",
        value=SHEET_URL_DEFAULT,
    )

def gsheet_append_row(payload: dict, sheet_url: str) -> bool:
    # Retorna True se sucesso, False se falhar
    client = get_gspread_client()
    if client is None:
        return False

    try:
        # Encontrar o spreadsheetId
        m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", sheet_url)
        if not m:
            st.error("Não consegui extrair o ID da planilha. Verifique a URL.")
            return False
        spreadsheet_id = m.group(1)

        sh = client.open_by_key(spreadsheet_id)
        # Tenta descobrir a aba pela 'gid' na URL
        gid_match = re.search(r"[?&]gid=(\d+)", sheet_url)
        ws = None
        if gid_match:
            target_gid = int(gid_match.group(1))
            for w in sh.worksheets():
                if w.id == target_gid:
                    ws = w
                    break
        if ws is None:
            # fallback: primeira aba
            ws = sh.sheet1

        # Garante cabeçalho
        header = [
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

        existing = ws.get_all_values()
        if not existing:
            ws.append_row(header, value_input_option="USER_ENTERED")

        # Ordena payload conforme header
        row = [payload.get(k, "") for k in header]
        ws.append_row(row, value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        st.error(f"Falha ao enviar para Google Sheets: {e}")
        return False

with st.form("envio_form"):
    submitted = st.form_submit_button("Enviar atualização")
    if submitted:
        # Se o usuário digitou novo telefone, opcionalmente salvar somente os dígitos:
        novo_fone_digits = only_digits(novo_fone) if novo_fone else ""

        payload = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_nascimento": dob.strftime("%d/%m/%Y"),
            "nome_do_filiado": selecionado.get(col_nome, ""),
            "email_atual": selecionado.get(col_email, ""),
            "celular_whatsapp_atual": str(selecionado.get(col_whats, "")),
            "corrigir_telefone_whatsapp": "Sim" if opt_fone else "Não",
            "novo_celular_whatsapp": novo_fone_digits,
            "corrigir_email": "Sim" if opt_mail else "Não",
            "novo_email": (novo_mail or ""),
            "setorial": setorial,
        }

        ok = gsheet_append_row(payload, sheet_url)
        if ok:
            st.success("✅ Envio realizado com sucesso!")
            st.json(payload)
            st.info("Dica: compartilhe a planilha com o e-mail do **Service Account** usado nas credenciais.")
        else:
            st.error("Não foi possível enviar para a planilha. Verifique as credenciais e dependências.")
