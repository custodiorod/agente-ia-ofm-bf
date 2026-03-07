# Agente IA - OFM
## Sistema de Automação Comercial com IA para WhatsApp

Sistema completo de automação de vendas e atendimento via WhatsApp com Inteligência Artificial.

---

## Características

- 🤖 **Agente Conversacional IA** - LangGraph com OpenRouter
- 🔄 **Follow-up Automático** - Sistema inteligente de acompanhamento
- 💰 **Pagamento via Pix** - Integração com PixBank
- 📊 **RAG (Retrieval-Augmented Generation)** - Base de conhecimento com pgvector
- 📈 **Observabilidade** - Integração com Langfuse
- ⚙️ **Orquestração** - Workflows com Kestra
- 🐳 **Docker** - Containers prontos para deploy

---

## Stack Tecnológico

### Backend
- **FastAPI** - Framework web assíncrono
- **LangGraph** - Orquestração de agentes IA
- **Celery** - Tarefas assíncronas
- **Redis** - Broker e cache
- **PostgreSQL + pgvector** - Banco de dados com embeddings

### IA & LLM
- **OpenRouter** - Acesso a múltiplos LLMs (Claude, GPT, etc)
- **LangChain** - Framework para LLMs
- **Faster Whisper** - Transcrição de áudio

### Serviços Externos
- **Supabase** - Banco de dados gerenciado
- **Uazapi** - API WhatsApp
- **PixBank** - Gateway Pix
- **Langfuse** - Observabilidade de IA
- **Kestra** - Orquestração de workflows

---

## Infraestrutura

- **VPS:** Hetzner (65.21.178.166)
- **Orquestrador:** Coolify
- **Repositório:** git@github.com:custodiorod/agente-ia-ofm-bf.git

---

## Deploy Automático

Toda vez que você fizer push para o GitHub, o Coolify irá automaticamente fazer o deploy na VPS.

```bash
git add .
git commit -m "Sua mensagem"
git push origin main
```

---

## Estrutura do Projeto

```
agente-ia-ofm-bf/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration
│   ├── api/                 # API endpoints
│   │   ├── health.py
│   │   ├── whatsapp_uazapi.py
│   │   └── pixbank.py
│   ├── agents/              # LangGraph agents
│   │   └── conversation_agent.py
│   ├── services/            # Business logic
│   │   ├── uazapi_service.py
│   │   ├── payment_service.py
│   │   ├── followup_service.py
│   │   ├── rag_service.py
│   │   ├── audio_service.py
│   │   └── langfuse_service.py
│   ├── tasks/               # Celery tasks
│   │   ├── worker.py
│   │   ├── message_tasks.py
│   │   ├── payment_tasks.py
│   │   └── followup_tasks.py
│   └── db/                  # Database models
│       ├── models.py
│       ├── session.py
│       └── migrations/
├── kestra/                  # Kestra workflows
│   ├── followup_dispatcher.yaml
│   ├── payment_reminder_flow.yaml
│   ├── upsell_after_payment.yaml
│   ├── reactivation_flow.yaml
│   └── dead_letter_reprocess.yaml
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

## Variáveis de Ambiente

Copie `.env.example` para `.env` e configure:

```bash
# Banco de Dados
DATABASE_URL=postgresql+asyncpg://...

# OpenRouter (LLM)
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=anthropic/claude-3-haiku

# WhatsApp Uazapi
UAZAPI_INSTANCE_ID=...
UAZAPI_API_TOKEN=...

# PixBank
PIXBANK_API_KEY=...
PIXBANK_SECRET_KEY=...

# Langfuse (Opcional)
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
```

---

## Desenvolvimento Local

```bash
# Clone o repositório
git clone git@github.com:custodiorod/agente-ia-ofm-bf.git
cd agente-ia-ofm-bf

# Copie as variáveis de ambiente
cp .env.example .env

# Edite o .env com suas credenciais
nano .env

# Suba os containers
docker-compose up -d
```

A API estará disponível em `http://localhost:8000`

---

## Endpoints da API

### Health Check
- `GET /health` - Status básico
- `GET /health/detailed` - Status detalhado dos serviços
- `GET /health/live` - Liveness probe
- `GET /health/ready` - Readiness probe

### Webhooks
- `GET /webhooks/whatsapp` - Verificação do webhook WhatsApp
- `POST /webhooks/whatsapp` - Receber mensagens WhatsApp
- `POST /webhooks/whatsapp/status` - Status de mensagens
- `POST /webhooks/pixbank/webhook` - Webhook PixBank

---

## Fluxo Principal

1. **Mensagem recebida** via WhatsApp (Uazapi)
2. **Webhook** chega na FastAPI
3. **Celery Worker** processa a mensagem
4. **LangGraph Agent** gera resposta
5. **RAG** busca contexto relevante (se necessário)
6. **Resposta** enviada via WhatsApp
7. **Follow-up** agendado automaticamente

---

## Licença

MIT
