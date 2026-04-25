#!/bin/bash

# Script pentru monitorizare logs E2E în timp real
# Afișează logs-uri pentru toate componentele importante

# Colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Fed-Med-FL E2E Logs Monitor${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}Alegeti ce logs doriti sa vedeti:${NC}"
echo ""
echo "1. Central Server (Flower Server)"
echo "2. Node1 Worker (Training)"
echo "3. Node2 Worker (Training)"
echo "4. Node1 API"
echo "5. Node2 API"
echo "6. Toate logs-urile (combined)"
echo "7. Doar Flower Server logs din fisier"
echo ""
read -p "Selectie (1-7): " choice

case $choice in
    1)
        echo -e "${GREEN}Monitorizare Central Server...${NC}"
        docker compose logs -f central
        ;;
    2)
        echo -e "${GREEN}Monitorizare Node1 Worker...${NC}"
        docker compose logs -f node1-worker
        ;;
    3)
        echo -e "${GREEN}Monitorizare Node2 Worker...${NC}"
        docker compose logs -f node2-worker
        ;;
    4)
        echo -e "${GREEN}Monitorizare Node1 API...${NC}"
        docker compose logs -f node1-api
        ;;
    5)
        echo -e "${GREEN}Monitorizare Node2 API...${NC}"
        docker compose logs -f node2-api
        ;;
    6)
        echo -e "${GREEN}Monitorizare toate serviciile...${NC}"
        docker compose logs -f central node1-worker node2-worker node1-api node2-api
        ;;
    7)
        echo -e "${GREEN}Monitorizare Flower Server logs...${NC}"
        echo "Verificare logs disponibile..."
        docker compose exec central ls -la /tmp/flower*.log 2>/dev/null || echo "Nu exista logs Flower inca"
        echo ""
        echo "Alegeti fisierul de logs:"
        echo "1. resnet18"
        echo "2. densenet121"
        echo "3. efficientnet_b0"
        read -p "Selectie (1-3): " model_choice
        
        case $model_choice in
            1) MODEL="resnet18" ;;
            2) MODEL="densenet121" ;;
            3) MODEL="efficientnet_b0" ;;
            *) MODEL="resnet18" ;;
        esac
        
        echo -e "${GREEN}Monitorizare /tmp/flower_${MODEL}.log...${NC}"
        docker compose exec central tail -f /tmp/flower_${MODEL}.log 2>/dev/null || echo "Fisierul nu exista inca"
        ;;
    *)
        echo -e "${YELLOW}Selectie invalida. Afisare toate logs-urile...${NC}"
        docker compose logs -f
        ;;
esac
