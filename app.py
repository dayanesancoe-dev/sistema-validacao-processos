# CÉLULA 1 - Instalar bibliotecas
!pip install -q streamlit google-generativeai PyPDF2

# CÉLULA 2 - Criar app.py corrigido
with open('app.py', 'w', encoding='utf-8') as f:
    f.write('''
import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime

st.set_page_config(page_title="Validação de Projetos", page_icon="🏛️", layout="wide")

st.title("🏛️ Sistema de Validação de Projetos")
st.markdown("**Prefeitura de Contagem** — Análise Inteligente com Google Gemini")

# Configuração API
st.header("⚙️ Configuração")
api_key = st.text_input("Cole sua API Key do Google Gemini:", type="password")

if api_key:
    st.success("✅ API configurada!")

    try:
        genai.configure(api_key=api_key)

        st.divider()
        st.header("📄 Upload de Documentos")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📐 PDFs do Projeto")
            projetos = st.file_uploader("Anexe os PDFs do projeto", type=['pdf'], accept_multiple_files=True, key="proj")

        with col2:
            st.subheader("📜 PDFs da Legislação")
            legislacoes = st.file_uploader("Anexe os PDFs da legislação", type=['pdf'], accept_multiple_files=True, key="leg")

        st.divider()
        st.header("📋 Dados do Processo")

        col1, col2, col3 = st.columns(3)

        with col1:
            numero = st.text_input("Número do Processo")
        with col2:
            requerente = st.text_input("Requerente")
        with col3:
            area = st.number_input("Área (m²)", min_value=0.0, step=0.1)

        st.divider()
        st.subheader("📏 Regras a Verificar")
        regras = st.text_area("Digite as regras (uma por linha):", height=150, placeholder="Ex:\\nArt. 10 - Área mínima 50m²")

        st.divider()

        if st.button("🔍 ANALISAR", type="primary", use_container_width=True):
            if projetos and legislacoes and numero and requerente and regras:
                with st.spinner("🤖 Analisando com IA..."):
                    try:
                        # Extrair textos
                        texto_proj = ""
                        for pdf in projetos:
                            reader = PyPDF2.PdfReader(pdf)
                            for page in reader.pages:
                                texto_proj += page.extract_text() + "\\n"

                        texto_leg = ""
                        for pdf in legislacoes:
                            reader = PyPDF2.PdfReader(pdf)
                            for page in reader.pages:
                                texto_leg += page.extract_text() + "\\n"

                        # MODELO CORRIGIDO: gemini-1.5-flash
                        model = genai.GenerativeModel('gemini-1.5-flash')

                        prompt = f"""Você é analista técnico da Prefeitura de Contagem - MG.

PROCESSO: {numero}
REQUERENTE: {requerente}
ÁREA: {area}m²

LEGISLAÇÃO:
{texto_leg[:4000]}

REGRAS A VERIFICAR:
{regras}

PROJETO:
{texto_proj[:6000]}

Analise detalhadamente:

## ✅ CONFORMIDADES
(cite artigos)

## ❌ NÃO CONFORMIDADES
(cite artigos e localize)

## ⚠️ PONTOS DE ATENÇÃO

## 🔧 RECOMENDAÇÕES

## 📊 PARECER
APROVADO ou REPROVADO (justifique)
"""

                        response = model.generate_content(prompt)

                        st.divider()
                        st.header("📋 RELATÓRIO")

                        if "APROVADO" in response.text and "REPROVADO" not in response.text:
                            st.success("✅ APROVADO")
                        elif "REPROVADO" in response.text:
                            st.error("❌ REPROVADO")

                        st.markdown(response.text)

                        # Download
                        relatorio = f"""PREFEITURA DE CONTAGEM
RELATÓRIO DE ANÁLISE

Processo: {numero}
Requerente: {requerente}
Área: {area}m²
Data: {datetime.now().strftime("%d/%m/%Y %H:%M")}

{response.text}
"""

                        st.download_button(
                            "📥 Baixar Relatório",
                            relatorio,
                            f"relatorio_{numero.replace('.', '_')}.txt",
                            use_container_width=True
                        )

                    except Exception as e:
                        st.error(f"❌ Erro: {str(e)}")
            else:
                st.error("❌ Preencha todos os campos!")

    except Exception as e:
        st.error(f"❌ Erro na API: {str(e)}")

else:
    st.info("👆 Cole sua API Key acima")
    st.markdown("[🔗 Obter API Key](https://aistudio.google.com/app/apikey)")

st.divider()
st.markdown("🏛️ **Sistema de Validação** • Prefeitura de Contagem")
''')

print("✅ app.py criado com sucesso!")

# CÉLULA 3 - Criar requirements.txt
with open('requirements.txt', 'w') as f:
    f.write('''streamlit
google-generativeai
PyPDF2
''')

print("✅ requirements.txt criado!")
