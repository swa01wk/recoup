# Recoup Frontend

Next.js app for the Recoup operator UI.

- **Project overview:** [../README.md](../README.md)
- **UI guide:** [../docs/frontend-guide.md](../docs/frontend-guide.md)
- **Local dev & E2E:** [../docs/local-dev-and-testing.md](../docs/local-dev-and-testing.md)

```bash
npm install
npm run dev          # http://localhost:3000
npx playwright test --grep @smoke
```

Set `NEXT_PUBLIC_API_URL` to match the backend (default **8000** with Docker; **8010** with native `.env.example`).
