# Sentra - Trust & Safety AI Engine

A production-grade Trust & Safety AI Engine that SaaS companies can integrate into their applications via API or SDK.

## Features

- **Content Moderation**
  - Text analysis (toxicity, hate speech, violence, spam)
  - Image moderation and deepfake detection
  - Video deepfake detection
  - Audio voice spoofing detection

- **Risk & Fraud Detection**
  - Multi-signal risk scoring (0-100)
  - Device fingerprinting
  - Behavioral anomaly analysis
  - Fraud pattern detection (phishing, scams, social engineering)

- **Enterprise-Ready**
  - RESTful API with OpenAPI documentation
  - Multi-platform SDKs (JavaScript, Python, React Native, Flutter)
  - Admin dashboard with real-time analytics
  - Scalable microservice architecture
  - Docker & Kubernetes deployment ready

## Quick Start

### Using Docker Compose

\`\`\`bash
# Clone repository
git clone https://github.com/Codedjaja/sentra.git
cd sentra

# Start services
make start

# Initialize database
make db-migrate
make db-seed
\`\`\`

Services will be available at:
- Backend API: http://localhost:3001
- Dashboard: http://localhost:3000

### Using the API

\`\`\`bash
# Moderate text
curl -X POST http://localhost:3001/api/moderate/text \
  -H "X-API-Key: sk_test_sentra_1234567890abcdef" \
  -H "Content-Type: application/json" \
  -d '{"content": "Text to moderate"}'

# Response
{
  "safe": true,
  "labels": [],
  "score": 5,
  "explanation": "Content appears safe"
}
\`\`\`

## Architecture

\`\`\`
┌─────────────────┐     ┌──────────────────┐
│  Dashboard UI   │────▶│   Backend API    │
│   (Next.js)     │     │   (Node.js/TS)   │
└─────────────────┘     └──────────────────┘
                               │
                               ├─────▶ PostgreSQL
                               ├─────▶ Redis Cache
                               └─────▶ AI Services
                                        (OpenAI/Anthropic)
\`\`\`

## SDKs

### JavaScript/TypeScript

\`\`\`bash
npm install @sentra/sdk
\`\`\`

\`\`\`typescript
import SentraClient from '@sentra/sdk'

const sentra = new SentraClient({ apiKey: 'YOUR_API_KEY' })
const result = await sentra.moderateText('Content to check')
\`\`\`

### Python

\`\`\`bash
pip install sentra-sdk
\`\`\`

\`\`\`python
from sentra import SentraClient

client = SentraClient(api_key='YOUR_API_KEY')
result = client.moderate_text('Content to check')
\`\`\`

### React Native & Flutter

See [SDKs documentation](./sdks/README.md) for more details.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| \`/api/moderate/text\` | POST | Moderate text content |
| \`/api/moderate/image\` | POST | Moderate images |
| \`/api/moderate/video\` | POST | Moderate videos |
| \`/api/moderate/audio\` | POST | Moderate audio |
| \`/api/risk/score\` | POST | Calculate risk score |
| \`/api/fraud/patterns\` | POST | Detect fraud patterns |
| \`/api/verify/deepfake\` | POST | Verify deepfakes |

Full API documentation: http://localhost:3001/api-docs

## Deployment

### Docker Compose
\`\`\`bash
docker-compose up -d
\`\`\`

### Kubernetes
\`\`\`bash
kubectl apply -f k8s/
\`\`\`

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed deployment instructions.

## Development

### Backend
\`\`\`bash
cd backend
npm install
npm run dev
\`\`\`

### Dashboard
\`\`\`bash
npm install
npm run dev
\`\`\`

### Run Tests
\`\`\`bash
make test
\`\`\`

## Configuration

### Environment Variables

See \`.env.example\` files in each directory for required configuration.

Key variables:
- \`OPENAI_API_KEY\` - OpenAI API key for text analysis
- \`ANTHROPIC_API_KEY\` - Anthropic API key (optional)
- \`JWT_SECRET\` - Secret for JWT authentication
- \`POSTGRES_*\` - Database connection settings
- \`REDIS_*\` - Redis connection settings

## Monitoring

Access monitoring dashboards:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3002

Default credentials:
- Username: admin
- Password: admin

## Security

- All API requests require authentication via API keys
- Rate limiting enforced (1000 req/hour default)
- Monthly quotas per organization
- Database encryption at rest
- TLS/SSL in production
- Row-level security (RLS) for multi-tenancy

## License

MIT License - see [LICENSE](./LICENSE) file

## Support

- Documentation: https://docs.sentra.ai
- Email: support@sentra.ai
- Discord: https://discord.gg/sentra
- GitHub Issues: https://github.com/your-org/sentra/issues
\`\`\`
