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
    regex_data_expedicao = r'aos\s+(\d{2}/\d{2}/\d{4})'

    padrao_rpv = re.compile(regex_rpv)
    padrao_processo = re.compile(regex_processo)
    padrao_cpf = re.compile(regex_cpf)
    padrao_valor = re.compile(regex_valor)
    padrao_data = re.compile(regex_data_expedicao, re.IGNORECASE)

    # 1º passo: mapeia cada RPV à sua data de expedição
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

    # 2º passo: extrai beneficiários
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

    df = pd.DataFrame(dados).drop_duplicates()
    return df


st.set_page_config(page_title="Extrator de RPVs", layout="wide")
st.title("Extrator de RPVs — Justiça Federal")
st.caption("Faça upload do PDF com os RPVs para gerar a planilha de beneficiários.")

arquivo = st.file_uploader("Selecione o arquivo PDF", type="pdf")

if arquivo:
    with st.spinner("Processando o PDF..."):
        df = extrair_dados_rpvs_escala(arquivo)

    st.success(f"Extração concluída: {len(df)} registros encontrados.")
    st.dataframe(df, use_container_width=True)

    saida = io.BytesIO()
    df.to_excel(saida, index=False)
    saida.seek(0)

    st.download_button(
        label="Baixar Excel",
        data=saida,
        file_name="Base_Consolidada.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
