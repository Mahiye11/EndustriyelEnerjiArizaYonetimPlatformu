# FactoryPulse

FactoryPulse is an industrial energy monitoring and maintenance demo. It receives machine telemetry, opens a single alarm when configured thresholds are exceeded, streams updates to a live dashboard, and produces date-filtered energy summaries.

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

Open http://localhost:3000. The API documentation is available at http://localhost:8000/docs.

Demo credentials: `admin@factorypulse.local` / `factorypulse`

Send one high measurement:

```bash
docker compose run --rm simulator python simulator.py --once --high
```

## Repository layout

- `apps/web`: Next.js dashboard
- `services/platform-api`: FastAPI telemetry, realtime, reporting, and demo workflow
- `services/identity-service`: Java 17 Spring Boot identity boundary
- `services/device-service`: Java 17 Spring Boot device boundary
- `services/alarm-service`: Java 17 Spring Boot alarm boundary
- `simulator`: Python machine simulator
- `contracts`: shared event and API examples
- `infra`: gateway configuration

The runnable local demo uses the FastAPI platform service so the full scenario works with one command. The Java modules establish the intended production service boundaries and can be split behind the gateway incrementally.

## API flow

1. Authenticate with `POST /api/v1/auth/login`.
2. Create devices and thresholds via `/api/v1/devices`.
3. Send idempotent readings to `POST /api/v1/measurements`.
4. Watch `/ws/factories/{factoryId}` for live measurement/alarm events.
5. Assign or resolve alarms and query `/api/v1/reports/energy`.

All timestamps are UTC. Errors use `{code, message, requestId}`.

