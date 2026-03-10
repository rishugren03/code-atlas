#!/usr/bin/env bash
set -euo pipefail

# ─── Colors ─────────────────────────────────────────────────
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🌌 CodeAtlas — Setup Script${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ─── Step 1: Environment file ───────────────────────────────
if [ ! -f .env ]; then
    echo -e "${YELLOW}📋 Copying .env.example to .env...${NC}"
    cp .env.example .env
    echo -e "${GREEN}   ✅ .env created${NC}"
else
    echo -e "${GREEN}   ✅ .env already exists${NC}"
fi

# ─── Step 2: Start Docker services ─────────────────────────
echo -e "\n${YELLOW}🐳 Starting Docker services...${NC}"
docker-compose up -d --build
echo -e "${GREEN}   ✅ All services started${NC}"

# ─── Step 3: Wait for services to be healthy ────────────────
echo -e "\n${YELLOW}⏳ Waiting for services to be healthy...${NC}"
sleep 10

# ─── Step 4: Run database migrations ───────────────────────
echo -e "\n${YELLOW}🗄️  Running database migrations...${NC}"
docker-compose exec backend alembic upgrade head
echo -e "${GREEN}   ✅ Migrations applied${NC}"

# ─── Step 5: Seed language data ─────────────────────────────
echo -e "\n${YELLOW}🌳 Seeding language family tree...${NC}"
docker-compose exec backend python -m scripts.seed_languages 2>/dev/null || \
    python scripts/seed_languages.py 2>/dev/null || \
    echo -e "${YELLOW}   ⚠️  Seed script skipped (run manually if needed)${NC}"

# ─── Done ───────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}🚀 CodeAtlas is ready!${NC}"
echo ""
echo -e "  Frontend:  ${BLUE}http://localhost:3000${NC}"
echo -e "  API:       ${BLUE}http://localhost:8000${NC}"
echo -e "  API Docs:  ${BLUE}http://localhost:8000/docs${NC}"
echo -e "  Neo4j:     ${BLUE}http://localhost:7474${NC}"
echo ""
