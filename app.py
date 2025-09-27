
import os
import io
import pandas as pd
import streamlit as st
from datetime import datetime, date
from typing import Optional, List

# === Optional: Google Sheets (gspread) ===
# We'll try to import gspread only when needed
def get_gspread_client():
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except Exception as e:
        st.error("Bibliotecas do Google não estão instaladas. Adicione 'gspread' e 'google-auth' ao requirements.txt.")
        return None

    if "gcp_service_account" not in st.secrets:
        st.error("As credenciais do Google não foram configuradas. Adicione st.secrets['gcp_service_account'].")
        return None

    creds_info = st.secrets["gcp_service_account"]
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = Credentials.from_service_account_info(creds_info, scopes=scope)
    client = gspread.authorize(credentials)
    return client

# ============ Configurações iniciais ============

st.set_page_config(page_title="Atualização de Contatos — Filiados", page_icon="🗂️", layout="centered")

st.markdown(
    """
    <style>
    .small { font-size: 0.9rem; color: #4b5563; }
    .ok { color: #065f46; }
    .warn { color: #92400e; }
    .err { color: #991b1b; }
    .card {
        border-radius: 14px;
        padding: 14px 16px;
        box-shadow: 0 4px 14px rgba(0,0,0,.08);
        background: #fff;
        border: 1px solid #eef2f7;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🗂️ Atualização de Contatos de Filiados")
st.caption("Consulte pelo **aniversário** e, se necessário, envie correções de contato para a planilha oficial.")

# ============ Entrada de dados base ============

@st.cache_data(show_spinner=False)
def load_csv(path_or_buffer) -> pd.DataFrame:
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

DEFAULT_CSV_PATH = "FILADOSDADOS.csv"
csv_source = None

# Tenta usar arquivo local se existir, senão aceita upload
if os.path.exists(DEFAULT_CSV_PATH):
    csv_source = DEFAULT_CSV_PATH
    st.success("Arquivo base encontrado: **FILADOSDADOS.csv**")
else:
    up = st.file_uploader("Envie a planilha .csv (separadores automáticos).", type=["csv"])
    if up:
        csv_source = io.BytesIO(up.read())

if not csv_source:
    st.stop()

with st.spinner("Carregando a base..."):
    df = load_csv(csv_source)

# Possíveis nomes de campos
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

df["_dn_date"] = df[col_dn].apply(to_date_safe)

# ============ Formulário de consulta ============

st.subheader("🔎 Consulta por data de nascimento")

dob = st.date_input("Data de nascimento", format="DD/MM/YYYY", value=None)
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
with st.container(border=True):
    st.write("**Nome do filiado:**", selecionado.get(col_nome, ""))
    st.write("**E-mail:**", selecionado.get(col_email, ""))
    st.write("**Celular/WhatsApp:**", selecionado.get(col_whats, ""))

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
st.caption("As respostas serão **anexadas** à planilha indicada, com cabeçalho na primeira linha se ainda não existir.")

sheet_url = st.text_input(
    "URL da Planilha Google (aba onde deseja registrar as respostas):",
    value="https://docs.google.com/spreadsheets/d/1tWyQQow2jhP50hSLSc00CvzfWVubpcd48MUeVvWTa_s/edit?gid=0",
)

def gsheet_append_row(payload: dict) -> bool:
    # Retorna True se sucesso, False se falhar
    client = get_gspread_client()
    if client is None:
        return False

    try:
        # Extrai IDs da URL
        import re
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
        else:
            # Se a primeira linha não parecer cabeçalho correto, não sobrescrevemos,
            # apenas continuamos a preencher nas linhas seguintes.
            pass

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
        payload = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_nascimento": dob.strftime("%d/%m/%Y"),
            "nome_do_filiado": selecionado.get(col_nome, ""),
            "email_atual": selecionado.get(col_email, ""),
            "celular_whatsapp_atual": selecionado.get(col_whats, ""),
            "corrigir_telefone_whatsapp": "Sim" if opt_fone else "Não",
            "novo_celular_whatsapp": (novo_fone or ""),
            "corrigir_email": "Sim" if opt_mail else "Não",
            "novo_email": (novo_mail or ""),
            "setorial": setorial,
        }

        ok = gsheet_append_row(payload)
        if ok:
            st.success("✅ Envio realizado com sucesso!")
            st.json(payload)
            st.info("Dica: compartilhe a planilha com o e-mail do **Service Account** usado nas credenciais.")
        else:
            st.error("Não foi possível enviar para a planilha. Verifique as credenciais e dependências.")
