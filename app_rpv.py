import streamlit as st
import pdfplumber
import re
import io
import pandas as pd


def extrair_dados_rpvs_escala(arquivo_pdf):
    regex_rpv = r'\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}|\d{4}\.\d{2}\.\d{2}\.\d{3}\.\d{6}'
    regex_processo = r'\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}|\d{2}\.\d{7}-\d{1}'
    regex_cpf = r'\d{3}\.\d{3}\.\d{3}-\d{2}'
    regex_valor = r'\d{1,3}(?:\.\d{3})*,\d{2}'
    regex_data_expedicao = r'Data-base[:\s]+(\d{2}/\d{2}/\d{4})'

    padrao_rpv = re.compile(regex_rpv)
    padrao_processo = re.compile(regex_processo)
    padrao_cpf = re.compile(regex_cpf)
    padrao_valor = re.compile(regex_valor)
    padrao_data = re.compile(regex_data_expedicao, re.IGNORECASE)

    datas_por_rpv = {}
    with pdfplumber.open(arquivo_pdf) as pdf:
        rpv_atual = None
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if not texto:
                continue
            for linha in texto.split('\n'):
                match_rpv = padrao_rpv.search(linha)
                if match_rpv:
                    rpv_atual = match_rpv.group()
                match_data = padrao_data.search(linha)
                if match_data and rpv_atual:
                    datas_por_rpv[rpv_atual] = match_data.group(1)

    dados = []
    with pdfplumber.open(arquivo_pdf) as pdf:
        numero_rpv_atual = None
        numero_processo_atual = None
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if not texto:
                continue
            for linha in texto.split('\n'):
                match_rpv = padrao_rpv.search(linha)
                if match_rpv:
                    numero_rpv_atual = match_rpv.group()

                match_processo = padrao_processo.search(linha)
                if match_processo:
                    numero_processo_atual = match_processo.group()

                match_cpf = padrao_cpf.search(linha)
                if match_cpf:
                    cpf = match_cpf.group()
                    idx = linha.index(cpf)
                    nome = re.sub(r'[^A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ\s]', '', linha[:idx]).strip()
                    apos = linha[idx + len(cpf):]
                    match_val = padrao_valor.search(apos)
                    valor = match_val.group() if match_val else None

                    if nome:
                        dados.append({
                            "Processo Origem": numero_processo_atual,
                            "RPV": numero_rpv_atual,
                            "Data Expedição": datas_por_rpv.get(numero_rpv_atual),
                            "Beneficiário": nome,
                            "CPF": cpf,
                            "Valor (R$)": valor,
                        })

    return pd.DataFrame(dados).drop_duplicates()


def valor_para_float(v):
    if not v:
        return 0.0
    try:
        return float(v.replace(".", "").replace(",", "."))
    except Exception:
        return 0.0


def gerar_excel(df):
    saida = io.BytesIO()
    df.to_excel(saida, index=False)
    saida.seek(0)
    return saida


def gerar_csv(df):
    return df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")


# ── Layout ──────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Extrator de RPVs", page_icon="🏛️", layout="wide")

st.title("🏛️ Extrator de RPVs — Justiça Federal")
st.caption("Faça upload do PDF com os RPVs para gerar a planilha de beneficiários.")
st.divider()

# Sidebar
with st.sidebar:
    st.header("📂 Upload do arquivo")
    arquivo = st.file_uploader("Selecione o PDF", type="pdf")
    st.divider()
    st.info("Formatos de exportação disponíveis: **Excel** e **CSV**.")

if not arquivo:
    st.info("Aguardando upload do PDF na barra lateral.")
    st.stop()

with st.spinner("Processando o PDF, aguarde..."):
    df = extrair_dados_rpvs_escala(arquivo)

if df.empty:
    st.warning("Nenhum registro encontrado no PDF.")
    st.stop()

# Métricas
total_beneficiarios = len(df)
total_rpvs = df["RPV"].nunique()
valor_total = sum(valor_para_float(v) for v in df["Valor (R$)"])

col1, col2, col3 = st.columns(3)
col1.metric("Beneficiários", f"{total_beneficiarios:,}".replace(",", "."))
col2.metric("RPVs", total_rpvs)
col3.metric("Valor Total", f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

st.divider()

# Filtro
rpvs_disponiveis = sorted(df["RPV"].dropna().unique())
rpv_selecionado = st.selectbox("Filtrar por RPV", options=["Todos"] + rpvs_disponiveis)

df_filtrado = df if rpv_selecionado == "Todos" else df[df["RPV"] == rpv_selecionado]

st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

st.divider()

# Exportação
st.subheader("📥 Exportar")
col_excel, col_csv = st.columns(2)

with col_excel:
    st.download_button(
        label="⬇️ Baixar Excel (.xlsx)",
        data=gerar_excel(df_filtrado),
        file_name="Base_Consolidada.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary",
    )

with col_csv:
    st.download_button(
        label="⬇️ Baixar CSV (.csv)",
        data=gerar_csv(df_filtrado),
        file_name="Base_Consolidada.csv",
        mime="text/csv",
        use_container_width=True,
    )
