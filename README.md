
# App Streamlit — Atualização de Contatos de Filiados

Este app lê um `.csv` de filiados, consulta por **data de nascimento** e permite enviar correções de contato para uma **Planilha Google**.

## Como executar

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Coloque sua planilha CSV na mesma pasta com o nome **FILADOSDADOS.csv**. Se preferir, você também pode **fazer upload** do CSV pela interface.

## Envio para Google Sheets

O app usa **gspread** com credenciais de **Service Account** configuradas em `st.secrets`. No Streamlit Cloud adicione em **App secrets** um campo JSON chamado `gcp_service_account` com o conteúdo das credenciais:
```toml
# .streamlit/secrets.toml
gcp_service_account = { /* conteúdo JSON do service account */ }
```

Localmente, você pode criar um arquivo `.streamlit/secrets.toml` com:
```toml
gcp_service_account = { /* JSON do service account */ }
```

> **Importante:** Compartilhe a planilha do Google com o e-mail do Service Account (algo como `xxx@yyy.iam.gserviceaccount.com`) com pelo menos permissão de **Editor**.

A URL da planilha pode ser a mesma do enunciado. O app detecta o **Spreadsheet ID** e tenta usar a aba correspondente ao `gid` informado na URL. Se não encontrar, usa a primeira aba.

Ao enviar, o app garante que a **primeira linha** terá o cabeçalho do formulário, caso a planilha esteja vazia.

## Campos esperados no CSV

O app tenta detectar automaticamente as colunas pelos seguintes nomes:

- Data de Nascimento: `data_de_nascimento`, `data_nascimento`, `data_nasc`, `nascimento`, `dt_nasc`, `dt_nascimento`
- Nome do Filiado: `nome_do_filiado`, `nome`, `nome_completo`
- E-mail: `e-mail`, `email`, `e_mail`
- Celular/WhatsApp: `celular_whatsapp`, `celular`, `telefone`, `telefone_whatsapp`, `whatsapp`

Se necessário, ajuste os nomes candidatos no código.

## Estrutura da linha enviada

- `timestamp`
- `data_nascimento`
- `nome_do_filiado`
- `email_atual`
- `celular_whatsapp_atual`
- `corrigir_telefone_whatsapp`
- `novo_celular_whatsapp`
- `corrigir_email`
- `novo_email`
- `setorial`

