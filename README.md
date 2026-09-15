🌊 FloodSense AI
<div align="center">
Sistema Inteligente de Monitoramento e Previsão de Enchentes Urbanas
<p> Uma solução acadêmica que integra <strong>IoT + ESP32 + Sensor Ultrassônico + Firebase + Dashboard Web + Análise de Dados</strong> </p> <br> <a href="https://leila533.github.io/floodsense-ai/"> <img src="https://img.shields.io/badge/🌊%20ACESSAR%20O%20SISTEMA-1597D4?style=for-the-badge" alt="Acessar FloodSense AI"> </a> <a href="https://github.com/leila533/floodsense-ai"> <img src="https://img.shields.io/badge/💻%20CÓDIGO-FONTE-172832?style=for-the-badge&logo=github" alt="Código fonte"> </a>

<br><br>

<img src="https://img.shields.io/badge/STATUS-MVP%20ACADÊMICO-16A36A?style=flat-square"> <img src="https://img.shields.io/badge/IoT-ESP32-1597D4?style=flat-square"> <img src="https://img.shields.io/badge/Firebase-Realtime%20Database-FFCA28?style=flat-square"> <img src="https://img.shields.io/badge/JavaScript-ES6-F7DF1E?style=flat-square"> <img src="https://img.shields.io/badge/Deploy-GitHub%20Pages-222222?style=flat-square&logo=github"> </div>
🌧️ Sobre o projeto

Como a tecnologia pode contribuir para o monitoramento de enchentes urbanas?

O FloodSense AI é um projeto acadêmico desenvolvido no curso de Sistemas de Informação da Universidade Paulista — UNIP, com o objetivo de explorar uma solução tecnológica para o monitoramento de níveis de água e identificação de situações de risco relacionadas a enchentes urbanas.

A proposta integra Internet das Coisas (IoT), sensores físicos, conectividade, armazenamento em nuvem e uma interface web, permitindo centralizar e visualizar informações de monitoramento.

<div align="center">
🎓 Projeto Acadêmico • UNIP • Sistemas de Informação • 2026
</div>
🚀 Acesse o FloodSense AI
<div align="center">
🌊 SISTEMA ONLINE
➡️ CLIQUE AQUI PARA ACESSAR O FLOODSENSE AI
<br>

Dashboard disponível diretamente pelo navegador.

</div>
🎯 Objetivo

O objetivo do FloodSense AI é desenvolver um protótipo de monitoramento de níveis de água, utilizando sensores conectados para coletar informações e disponibilizá-las em uma interface web.

A solução busca demonstrar, em um cenário acadêmico, como diferentes tecnologias podem ser integradas para apoiar o acompanhamento de situações relacionadas a enchentes urbanas.

💡 Como funciona?

O sistema é estruturado em um fluxo de coleta, transmissão, armazenamento e visualização de dados:

        📡 SENSOR
        AJ-SR04M
            │
            ▼
       🔌 ESP32
    Coleta dos dados
            │
          Wi-Fi
            │
            ▼
     ☁️ FIREBASE
   Realtime Database
            │
            ▼
      🖥️ DASHBOARD
       FloodSense AI
            │
            ▼
      🚨 MONITORAMENTO
        E ANÁLISE
📡 Protótipo IoT

Um dos principais diferenciais do projeto é a utilização de um protótipo físico real.

🔌 Componentes
Componente	Função
🔌 ESP32	Coleta e processamento das informações
📏 AJ-SR04M	Medição ultrassônica
📶 Wi-Fi	Comunicação do ESP32
☁️ Firebase	Armazenamento e disponibilização dos dados
🔄 Fluxo do protótipo
📏 AJ-SR04M
     ↓
🔌 ESP32
     ↓
📶 Wi-Fi
     ↓
☁️ Firebase
     ↓
🖥️ Dashboard

O sensor realiza medições físicas e o ESP32 transmite as informações para o Firebase, permitindo sua visualização no dashboard.

📊 Funcionalidades
<div align="center">
🌊 Monitoramento	📡 IoT	☁️ Cloud	🚨 Alertas
Nível da água	ESP32	Firebase	Status de risco
Distância medida	AJ-SR04M	Dados em tempo real	Indicadores
Status do sensor	Wi-Fi	Realtime Database	Comunicação
🗺️ Visualização	🤖 Inteligência	📈 Análise	📱 Comunicação
Mapa interativo	Previsões	Gráficos	WhatsApp
Dashboard	Machine Learning	Indicadores	Ocorrências
</div>
🖥️ Dashboard

O FloodSense AI possui uma interface web centralizada para apresentação das informações do sistema.

Principais módulos
┌──────────────────────────────────────────┐
│              🌊 FLOODSENSE AI            │
├──────────────────────────────────────────┤
│                                          │
│  📊 Dashboard                            │
│                                          │
│  📡 Sensores IoT                         │
│                                          │
│  🗺️ Mapa Interativo                      │
│                                          │
│  🤖 IA & Previsões                       │
│                                          │
│  📈 Análise Gráfica                      │
│                                          │
│  🚨 Alertas                              │
│                                          │
│  📄 Relatórios                           │
│                                          │
│  ⚙️ Configurações                        │
│                                          │
└──────────────────────────────────────────┘
Informações apresentadas
💧 Nível da água
📏 Distância medida
📡 Status do sensor
☁️ Conexão com Firebase
🚨 Alertas
🗺️ Mapa interativo
📈 Indicadores e gráficos
🤖 Área de IA e previsões
📱 Comunicação de ocorrências
🤖 Inteligência Artificial

O projeto possui uma proposta de utilização de Inteligência Artificial e Machine Learning para análise de dados e apoio à identificação de situações de risco relacionadas a enchentes.

A aplicação dessas técnicas faz parte da proposta tecnológica do FloodSense AI.

ℹ️ Transparência do protótipo: algumas informações apresentadas no dashboard são simuladas ou demonstrativas, pois o projeto encontra-se em fase de MVP/protótipo acadêmico.

Dessa forma, o FloodSense AI não é apresentado como uma plataforma operacional de previsão de enchentes em produção, mas como uma prova de conceito acadêmica.

☁️ Arquitetura tecnológica
┌──────────────────────┐
│       📡 SENSOR      │
│       AJ-SR04M       │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│       🔌 ESP32       │
│        IoT           │
└──────────┬───────────┘
           │
         Wi-Fi
           │
           ▼
┌──────────────────────┐
│     ☁️ FIREBASE      │
│   Realtime Database  │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│    🖥️ DASHBOARD      │
│         WEB          │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   🚨 ANÁLISE E       │
│       ALERTAS        │
└──────────────────────┘
🔐 Segurança

A segurança faz parte dos conceitos considerados na proposta do FloodSense AI.

🛡️ Conceitos considerados
🔐 Segurança	Aplicação
🔒 Proteção de dados	Consideração na arquitetura
🛡️ Controle de acesso	Conceito previsto
🔐 Comunicação segura	Consideração na transmissão
✅ Validação	Tratamento das informações
☁️ Segurança de infraestrutura	Consideração no ambiente cloud

⚠️ Importante: o FloodSense AI é um protótipo acadêmico. Algumas configurações utilizadas durante os testes foram simplificadas para facilitar a demonstração. Uma implementação em produção exigiria autenticação, regras de acesso adequadas, gerenciamento seguro de credenciais, validação dos dados e outros mecanismos de segurança.

🧪 Validação do protótipo

O protótipo físico foi utilizado para validar a comunicação entre o sensor, o ESP32, o Firebase e o dashboard.

Fluxo validado
📏 Sensor
    ↓
🔌 ESP32
    ↓
📶 Wi-Fi
    ↓
☁️ Firebase
    ↓
🖥️ Dashboard

Durante os testes, o sensor realizou leituras físicas e o ESP32 transmitiu os dados para o Firebase, possibilitando a visualização dessas informações na interface web.

📱 Comunicação de ocorrências

O dashboard também disponibiliza uma opção de comunicação de ocorrência por WhatsApp, permitindo direcionar o usuário para um canal de comunicação.

<div align="center">
🚨 Identificou uma ocorrência?

📱 FALAR PELO WHATSAPP

</div>
🛠️ Tecnologias
<div align="center">
Categoria	Tecnologias
🔌 Hardware	ESP32 • AJ-SR04M
🌐 Front-end	HTML5 • CSS3 • JavaScript
☁️ Cloud	Firebase Realtime Database
📦 Runtime	Node.js
💻 Desenvolvimento	Visual Studio Code
📚 Versionamento	Git • GitHub
🚀 Deploy	GitHub Pages
</div>
📁 Estrutura do projeto
floodsense-ai/
│
├── 📁 assets/
│
├── 📁 firmware/
│
├── 📄 index.html
├── 📄 script.js
├── 🎨 style.css
├── 📦 package.json
└── 📦 package-lock.json
👥 Equipe
👩‍💻 Leila Victoria Lima Borges
Desenvolvimento e integração do sistema

Responsável pela implementação e integração das principais partes técnicas do projeto:

💻 Desenvolvimento do sistema web
🖥️ Desenvolvimento e estruturação do dashboard
🔌 Implementação do protótipo físico
📡 Integração ESP32 + sensor
☁️ Integração ESP32 + Firebase
🧪 Testes e validação
🛠️ Correções e ajustes do sistema
🎨 Correção e revisão dos slides
📄 Revisão e ajustes da documentação
🎤 Montagem e organização da apresentação
🔗 Integração geral dos componentes do projeto
👨‍💻 Pedro Gustavo Figueira Bezerra
Slides e apresentação

Responsável principalmente pela preparação dos materiais visuais e participação na apresentação:

🎨 Elaboração dos slides
📊 Organização do material visual
📝 Estruturação da apresentação
🎤 Participação na apresentação oral
👨‍💻 Vagner de Araújo Lima
Documentação e apresentação

Responsável principalmente pela documentação do projeto:

📄 Desenvolvimento da documentação
📝 Organização das informações técnicas
📚 Estruturação documental
🎤 Participação na apresentação oral
🎤 Apresentação do TCC

A apresentação oral do projeto será realizada por:

<div align="center">
👨‍💻 Pedro Gustavo Figueira Bezerra
👨‍💻 Vagner de Araújo Lima
</div>

Os integrantes apresentarão o projeto em nome da equipe durante a avaliação acadêmica.

A preparação final dos materiais, organização da apresentação e integração do projeto foram realizadas no desenvolvimento do trabalho.

🎓 Instituição
<div align="center">
UNIVERSIDADE PAULISTA — UNIP
Sistemas de Informação

2026

<br>

🌊 FloodSense AI

Tecnologia para transformar dados em informação e apoiar o monitoramento de enchentes urbanas.

</div>
📌 Status do projeto
<div align="center">
🟢 MVP / PROTÓTIPO ACADÊMICO
<br>

Hardware
↓
IoT
↓
Cloud
↓
Dashboard Web
↓
Análise de Dados

<br>

O FloodSense AI encontra-se em desenvolvimento como uma prova de conceito acadêmica, demonstrando a integração entre hardware, software, armazenamento em nuvem e visualização de dados.

</div>
🌊 FloodSense AI
<div align="center">
Transformando dados em informação para apoiar o monitoramento de enchentes urbanas.
<br>

🚀 ACESSAR O SISTEMA

<br><br>

UNIP • Sistemas de Informação • 2026

</div>
