"""
Tribal Wars Mobile Automation Engine - MarketManager (screen=market)
Gestão do Mercado: leitura de mercadores (disponíveis, totais, em trânsito),
algoritmo de balanceamento automatizado de recursos entre aldeias da mesma conta
e criação de ofertas no mercado local para troca de excedentes.
"""

from dataclasses import asdict, dataclass, field
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from engine.core.account import TribalAccount
from engine.utils.parsers import parse_market_offers, parse_market_screen

logger = logging.getLogger("TribalWars.Market")


@dataclass
class MerchantMovement:
    """Representação de um transporte de recursos a caminho (chegada ou partida)."""
    direction: str  # "outgoing" (a enviar) ou "incoming" (a receber)
    village_id: int
    village_name: str
    coords: Tuple[int, int]
    wood: int
    stone: int
    iron: int
    total_resources: int
    arrival_time: str
    merchants_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MarketOffer:
    """Representação de uma oferta de troca de recursos no mercado."""
    id: int
    sell_res: str      # "wood", "stone", "iron"
    sell_amount: int
    buy_res: str       # "wood", "stone", "iron"
    buy_amount: int
    ratio: float       # ex: 1.0
    available_offers: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MarketState:
    """Estado do mercado numa determinada aldeia."""
    village_id: int
    merchants_available: int = 0
    merchants_total: int = 0
    carry_capacity_per_merchant: int = 1000
    transports: List[MerchantMovement] = field(default_factory=list)
    own_offers: List[MarketOffer] = field(default_factory=list)
    last_updated: float = 0.0

    @property
    def merchants_in_transit(self) -> int:
        return max(0, self.merchants_total - self.merchants_available)

    @property
    def total_resources_in_transit(self) -> int:
        return sum(t.total_resources for t in self.transports)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "village_id": self.village_id,
            "merchants_available": self.merchants_available,
            "merchants_total": self.merchants_total,
            "merchants_in_transit": self.merchants_in_transit,
            "carry_capacity_per_merchant": self.carry_capacity_per_merchant,
            "transports": [t.to_dict() for t in self.transports],
            "own_offers": [o.to_dict() for o in self.own_offers],
            "last_updated": self.last_updated,
        }


@dataclass
class TransferOrder:
    """Ordem calculada de transferência de recursos entre duas aldeias."""
    source_village_id: int
    source_name: str
    source_coords: Tuple[int, int]
    target_village_id: int
    target_name: str
    target_coords: Tuple[int, int]
    wood: int
    stone: int
    iron: int
    merchants_required: int
    reason: str

    @property
    def total_resources(self) -> int:
        return self.wood + self.stone + self.iron

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_village_id": self.source_village_id,
            "source_name": self.source_name,
            "source_coords": f"{self.source_coords[0]}|{self.source_coords[1]}",
            "target_village_id": self.target_village_id,
            "target_name": self.target_name,
            "target_coords": f"{self.target_coords[0]}|{self.target_coords[1]}",
            "wood": self.wood,
            "stone": self.stone,
            "iron": self.iron,
            "total_resources": self.total_resources,
            "merchants_required": self.merchants_required,
            "reason": self.reason,
        }


class MarketManager:
    """
    Controlador do Mercado (screen=market).
    Executa leituras de mercadores, ordens de transporte e o algoritmo
    de balanceamento de recursos entre aldeias da mesma conta.
    """

    CARRY_PER_MERCHANT = 1000  # 1 mercador transporta exatamente 1.000 recursos

    def __init__(self):
        self._states: Dict[int, MarketState] = {}
        self.last_balancing_time: float = 0.0

    async def get_market_state(
        self,
        account: TribalAccount,
        village_id: Optional[int] = None,
        include_offers: bool = False,
    ) -> MarketState:
        """
        Carrega o ecrã do mercado (screen=market) da aldeia e atualiza o estado em memória.
        """
        v_id = village_id or account.current_village_id or 0
        now = time.time()

        try:
            html = await account.get_screen("market", village_id=v_id)
        except Exception as e:
            logger.warning(f"[{account.world}] Falha ao carregar 'screen=market' para aldeia {v_id}: {e}")
            html = ""

        data = parse_market_screen(html)

        transports: List[MerchantMovement] = []
        for t in data.get("transports", []):
            transports.append(
                MerchantMovement(
                    direction=t.get("direction", "incoming"),
                    village_id=t.get("village_id", 0),
                    village_name=t.get("village_name", ""),
                    coords=t.get("coords", (0, 0)),
                    wood=t.get("wood", 0),
                    stone=t.get("stone", 0),
                    iron=t.get("iron", 0),
                    total_resources=t.get("total_resources", 0),
                    arrival_time=t.get("arrival_time", ""),
                    merchants_count=t.get("merchants_count", 1),
                )
            )

        own_offers: List[MarketOffer] = []
        if include_offers:
            try:
                offers_html = await account.get_screen("market", village_id=v_id, extra_params={"mode": "own_offer"})
                for o in parse_market_offers(offers_html):
                    own_offers.append(
                        MarketOffer(
                            id=o.get("id", 0),
                            sell_res=o.get("sell_res", "wood"),
                            sell_amount=o.get("sell_amount", 1000),
                            buy_res=o.get("buy_res", "stone"),
                            buy_amount=o.get("buy_amount", 1000),
                            ratio=o.get("ratio", 1.0),
                            available_offers=o.get("available_offers", 1),
                        )
                    )
            except Exception as e:
                logger.debug(f"[{account.world}] Falha ao carregar ofertas próprias no mercado: {e}")

        state = MarketState(
            village_id=v_id,
            merchants_available=data.get("merchants_available", 0),
            merchants_total=data.get("merchants_total", 0),
            carry_capacity_per_merchant=self.CARRY_PER_MERCHANT,
            transports=transports,
            own_offers=own_offers,
            last_updated=now,
        )

        self._states[v_id] = state
        return state

    async def send_resources(
        self,
        account: TribalAccount,
        source_village_id: int,
        target_village_id: int,
        wood: int = 0,
        stone: int = 0,
        iron: int = 0,
    ) -> bool:
        """
        Envia recursos da aldeia de origem para a aldeia de destino via mercadores.
        Valida mercadores disponíveis, recursos existentes e limites de armazém.
        """
        total_res = wood + stone + iron
        if total_res <= 0:
            logger.warning(f"[{account.world}] Pedido de envio com 0 recursos.")
            return False

        merchants_needed = max(1, (total_res + self.CARRY_PER_MERCHANT - 1) // self.CARRY_PER_MERCHANT)

        source_v = account.villages.get(source_village_id)
        target_v = account.villages.get(target_village_id)

        if not source_v or not target_v:
            logger.warning(
                f"[{account.world}] Aldeias inválidas para envio: origem={source_village_id}, destino={target_village_id}"
            )
            return False

        # Validação de recursos locais na origem
        if (
            source_v.resources.wood < wood
            or source_v.resources.stone < stone
            or source_v.resources.iron < iron
        ):
            logger.warning(
                f"[{account.world}] Recursos insuficientes na aldeia {source_village_id} para enviar: "
                f"req=({wood}W, {stone}S, {iron}I) vs disp=({source_v.resources.wood}W, {source_v.resources.stone}S, {source_v.resources.iron}I)"
            )
            return False

        # Validação de capacidade do armazém no destino (prevenção de transbordamento)
        storage_max = target_v.resources.storage_max
        if storage_max > 0:
            free_room = max(0, storage_max - max(target_v.resources.wood, target_v.resources.stone, target_v.resources.iron))
            # Garante que nenhum recurso excederá o armazém
            if (
                target_v.resources.wood + wood > storage_max
                or target_v.resources.stone + stone > storage_max
                or target_v.resources.iron + iron > storage_max
            ):
                logger.warning(
                    f"[{account.world}] Armazém da aldeia de destino {target_village_id} transbordaria! "
                    f"Armazém={storage_max}, recursos atuais=({target_v.resources.wood}W, {target_v.resources.stone}S, {target_v.resources.iron}I)"
                )
                # Ajusta para caber no armazém
                wood = min(wood, max(0, storage_max - target_v.resources.wood))
                stone = min(stone, max(0, storage_max - target_v.resources.stone))
                iron = min(iron, max(0, storage_max - target_v.resources.iron))
                total_res = wood + stone + iron
                if total_res <= 0:
                    return False
                merchants_needed = max(1, (total_res + self.CARRY_PER_MERCHANT - 1) // self.CARRY_PER_MERCHANT)

        # Validação de mercadores disponíveis
        state = self._states.get(source_village_id)
        if not state:
            state = await self.get_market_state(account, source_village_id)

        if state.merchants_available < merchants_needed:
            logger.warning(
                f"[{account.world}] Mercadores insuficientes na aldeia {source_village_id}: "
                f"necessários={merchants_needed}, disponíveis={state.merchants_available}"
            )
            return False

        # Despacho via POST para screen=market&action=send
        data = {
            "target_id": target_village_id,
            "x": target_v.x,
            "y": target_v.y,
            "wood": wood,
            "stone": stone,
            "iron": iron,
        }

        try:
            logger.info(
                f"[{account.world}] A enviar {wood}W, {stone}S, {iron}I ({merchants_needed} mercadores) "
                f"de {source_v.name} ({source_v.coordinates}) para {target_v.name} ({target_v.coordinates})..."
            )
            resp = await account.post_action(
                screen="market",
                action="send",
                village_id=source_village_id,
                data=data,
            )
            # Atualiza o estado dos recursos localmente
            source_v.resources.wood = max(0, source_v.resources.wood - wood)
            source_v.resources.stone = max(0, source_v.resources.stone - stone)
            source_v.resources.iron = max(0, source_v.resources.iron - iron)

            state.merchants_available = max(0, state.merchants_available - merchants_needed)
            return True
        except Exception as e:
            logger.error(f"[{account.world}] Erro ao enviar mercadores: {e}")
            return False

    def calculate_balancing_transfers(
        self,
        account: TribalAccount,
        reserve_margin: float = 0.20,
        overflow_threshold: float = 0.90,
        deficit_threshold: float = 0.30,
        min_transfer_amount: int = 1000,
        max_merchant_ratio: float = 0.80,
    ) -> List[TransferOrder]:
        """
        Algoritmo Matemático de Balanceamento Global de Recursos.
        - Analisa as aldeias pertencentes à conta.
        - Identifica doadoras com excedente ou risco iminente de armazém cheio (>= 90%).
        - Identifica recetoras com défice acentuado (<= 30% ou abaixo da média).
        - Arredonda em múltiplos de 1.000 (1 mercador por lote).
        - Evita transbordamento do armazém da aldeia de destino.
        """
        villages = list(account.villages.values())
        if len(villages) < 2:
            return []

        # 1. Médias de recursos da conta
        total_w = sum(v.resources.wood for v in villages)
        total_s = sum(v.resources.stone for v in villages)
        total_i = sum(v.resources.iron for v in villages)
        n = len(villages)

        avg_w = total_w / n
        avg_s = total_s / n
        avg_i = total_i / n

        orders: List[TransferOrder] = []

        # Rastreamento de mercadores disponíveis por aldeia doadora
        merchants_remaining: Dict[int, int] = {}
        for v in villages:
            m_state = self._states.get(v.id)
            avail_m = m_state.merchants_available if m_state else (v.resources.storage_max // 1000)
            merchants_remaining[v.id] = int(avail_m * max_merchant_ratio)

        # Para cada tipo de recurso (wood, stone, iron)
        for res_type, avg_val in [("wood", avg_w), ("stone", avg_s), ("iron", avg_i)]:
            donors = []
            receivers = []

            for v in villages:
                res_val = getattr(v.resources, res_type)
                storage_max = v.resources.storage_max or 10000
                reserve = storage_max * reserve_margin
                overflow_mark = storage_max * overflow_threshold
                deficit_mark = min(avg_val, storage_max * deficit_threshold)

                # Doadora: excedente acima da média e da reserva de segurança OU armazém quase cheio
                if res_val >= overflow_mark or (res_val > avg_val and res_val > reserve):
                    surplus = res_val - max(reserve, avg_val) if res_val < overflow_mark else res_val - (storage_max * 0.70)
                    if surplus >= min_transfer_amount:
                        donors.append({
                            "village": v,
                            "surplus": surplus,
                        })

                # Recetora: défice abaixo da média ou abaixo do limiar de segurança
                elif res_val < deficit_mark:
                    deficit = avg_val - res_val
                    room_in_storage = max(0, (storage_max * 0.90) - res_val)
                    needed = min(deficit, room_in_storage)
                    if needed >= min_transfer_amount:
                        receivers.append({
                            "village": v,
                            "needed": needed,
                        })

            # Ordena: doadoras com maior excedente primeiro, recetoras com maior necessidade primeiro
            donors.sort(key=lambda d: d["surplus"], reverse=True)
            receivers.sort(key=lambda r: r["needed"], reverse=True)

            d_idx = 0
            r_idx = 0

            while d_idx < len(donors) and r_idx < len(receivers):
                donor = donors[d_idx]
                receiver = receivers[r_idx]

                if donor["village"].id == receiver["village"].id:
                    d_idx += 1
                    continue

                # Capacidade de mercadores da doadora
                donor_v_id = donor["village"].id
                avail_merchants = merchants_remaining.get(donor_v_id, 0)
                if avail_merchants <= 0:
                    d_idx += 1
                    continue

                max_send_by_merchants = avail_merchants * self.CARRY_PER_MERCHANT

                sendable = min(donor["surplus"], receiver["needed"], max_send_by_merchants)
                # Quantiza em múltiplos de 1.000 (1 mercador por lote)
                quantized = (int(sendable) // self.CARRY_PER_MERCHANT) * self.CARRY_PER_MERCHANT

                if quantized >= min_transfer_amount:
                    merchants_needed = quantized // self.CARRY_PER_MERCHANT
                    reason = f"Excedente de {res_type.capitalize()} ({quantized}) -> Equilíbrio da conta"

                    # Monta ordem
                    w_amt = quantized if res_type == "wood" else 0
                    s_amt = quantized if res_type == "stone" else 0
                    i_amt = quantized if res_type == "iron" else 0

                    orders.append(
                        TransferOrder(
                            source_village_id=donor["village"].id,
                            source_name=donor["village"].name,
                            source_coords=donor["village"].coords_tuple,
                            target_village_id=receiver["village"].id,
                            target_name=receiver["village"].name,
                            target_coords=receiver["village"].coords_tuple,
                            wood=w_amt,
                            stone=s_amt,
                            iron=i_amt,
                            merchants_required=merchants_needed,
                            reason=reason,
                        )
                    )

                    donor["surplus"] -= quantized
                    receiver["needed"] -= quantized
                    merchants_remaining[donor_v_id] -= merchants_needed

                if donor["surplus"] < min_transfer_amount or merchants_remaining.get(donor_v_id, 0) <= 0:
                    d_idx += 1
                if receiver["needed"] < min_transfer_amount:
                    r_idx += 1

        return orders

    async def run_balancing_cycle(
        self,
        account: TribalAccount,
        reserve_margin: float = 0.20,
        overflow_threshold: float = 0.90,
        deficit_threshold: float = 0.30,
        min_transfer_amount: int = 1000,
        max_merchant_ratio: float = 0.80,
    ) -> Dict[str, Any]:
        """
        Executa um ciclo coordenado de balanceamento de recursos para todas as aldeias da conta.
        """
        # Atualiza o estado do mercado para cada aldeia
        for v_id in account.villages.keys():
            await self.get_market_state(account, v_id)

        orders = self.calculate_balancing_transfers(
            account=account,
            reserve_margin=reserve_margin,
            overflow_threshold=overflow_threshold,
            deficit_threshold=deficit_threshold,
            min_transfer_amount=min_transfer_amount,
            max_merchant_ratio=max_merchant_ratio,
        )

        executed = 0
        failed = 0

        logger.info(f"[{account.world}] Ciclo de Balanceamento de Recursos: {len(orders)} transferências planeadas.")

        for order in orders:
            success = await self.send_resources(
                account=account,
                source_village_id=order.source_village_id,
                target_village_id=order.target_village_id,
                wood=order.wood,
                stone=order.stone,
                iron=order.iron,
            )
            if success:
                executed += 1
            else:
                failed += 1

        self.last_balancing_time = time.time()
        return {
            "status": "success",
            "total_orders": len(orders),
            "executed": executed,
            "failed": failed,
            "orders": [o.to_dict() for o in orders],
        }

    async def create_market_offer(
        self,
        account: TribalAccount,
        village_id: int,
        sell_res: str,
        sell_amount: int,
        buy_res: str,
        buy_amount: int,
        max_time: int = 10,
        multi: int = 1,
    ) -> bool:
        """
        Publica uma oferta no mercado próprio da aldeia (screen=market&mode=own_offer&action=new_offer).
        """
        sell_res = sell_res.lower().strip()
        buy_res = buy_res.lower().strip()

        if sell_res not in ("wood", "stone", "iron") or buy_res not in ("wood", "stone", "iron"):
            logger.warning(f"[{account.world}] Tipos de recursos inválidos para oferta: {sell_res} / {buy_res}")
            return False

        if sell_res == buy_res or sell_amount <= 0 or buy_amount <= 0:
            logger.warning(f"[{account.world}] Valores ou recursos idênticos para oferta de mercado.")
            return False

        payload = {
            "res_sell": sell_res,
            "sell": sell_amount,
            "res_buy": buy_res,
            "buy": buy_amount,
            "max_time": max_time,
            "multi": multi,
        }

        try:
            logger.info(
                f"[{account.world}] A criar oferta no mercado ({multi}x): Vender {sell_amount} {sell_res} por {buy_amount} {buy_res}..."
            )
            await account.post_action(
                screen="market",
                action="new_offer",
                village_id=village_id,
                data=payload,
                extra_params={"mode": "own_offer"},
            )
            return True
        except Exception as e:
            logger.error(f"[{account.world}] Erro ao publicar oferta no mercado: {e}")
            return False

    async def auto_trade_excess_resources(
        self,
        account: TribalAccount,
        village_id: int,
        ratio: float = 1.0,
    ) -> int:
        """
        Deteta desequilíbrios internos de recursos numa aldeia individual e
        publica ofertas de troca 1:1 para converter o recurso abundante no escasso.
        """
        v = account.villages.get(village_id)
        if not v:
            return 0

        res_dict = {
            "wood": v.resources.wood,
            "stone": v.resources.stone,
            "iron": v.resources.iron,
        }

        sorted_res = sorted(res_dict.items(), key=lambda item: item[1])
        scarcest_res, scarcest_val = sorted_res[0]
        abundant_res, abundant_val = sorted_res[2]

        diff = abundant_val - scarcest_val
        storage_max = v.resources.storage_max or 10000

        # Só gera ofertas se a diferença for substancial (> 3000) e o excedente for relevante
        if diff >= 3000 and abundant_val >= (storage_max * 0.35):
            state = await self.get_market_state(account, village_id, include_offers=True)
            if state.merchants_available <= 0:
                return 0

            max_offers = min(state.merchants_available, diff // 2000, 5)
            if max_offers >= 1:
                sell_amt = 1000
                buy_amt = int(sell_amt * ratio)
                success = await self.create_market_offer(
                    account=account,
                    village_id=village_id,
                    sell_res=abundant_res,
                    sell_amount=sell_amt,
                    buy_res=scarcest_res,
                    buy_amount=buy_amt,
                    max_time=12,
                    multi=max_offers,
                )
                if success:
                    return max_offers

        return 0
