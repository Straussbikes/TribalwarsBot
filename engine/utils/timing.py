"""
Tribal Wars Mobile Automation Engine - Utilitários de Temporização Humana
Gera atrasos aleatórios com distribuição normal (gaussiana) truncada e micro-jitters
para evitar deteções heurísticas por regularidade temporal.
"""

import random
import time


def get_human_delay(
    base_seconds: float,
    std_dev: float,
    min_seconds: float,
    max_seconds: float,
) -> float:
    """
    Calcula um atraso baseado numa distribuição gaussiana truncada.
    
    :param base_seconds: Média desejada (mu).
    :param std_dev: Desvio padrão (sigma) representando a variância natural humana.
    :param min_seconds: Limite inferior estrito (impede atrasos negativos ou sobre-humanos).
    :param max_seconds: Limite superior estrito (evita tempos de espera excessivos).
    :return: Atraso em segundos com precisão de milissegundos.
    """
    if min_seconds >= max_seconds:
        raise ValueError("min_seconds deve ser estritamente menor que max_seconds")
    if base_seconds < min_seconds or base_seconds > max_seconds:
        # Ajusta a média para o intervalo se configurada fora
        base_seconds = max(min_seconds, min(base_seconds, max_seconds))

    # Amostragem da curva gaussiana com truncagem (rejection sampling com limite de tentativas)
    for _ in range(10):
        val = random.gauss(base_seconds, std_dev)
        if min_seconds <= val <= max_seconds:
            # Adiciona uma micro-flutuação de milissegundos impercetível
            micro_jitter = random.uniform(-0.02, 0.02)
            final_delay = round(max(min_seconds, min(val + micro_jitter, max_seconds)), 3)
            return final_delay

    # Fallback caso a amostragem exceda as iterações (clamp direto)
    return round(max(min_seconds, min(val, max_seconds)), 3)


def get_click_jitter(min_ms: float = 120.0, max_ms: float = 380.0) -> float:
    """
    Simula o tempo de reação mecânico humano entre toques num ecrã táctil mobile.
    
    :return: Tempo em segundos (ex.: 0.120s a 0.380s).
    """
    mu = (min_ms + max_ms) / 2.0
    sigma = (max_ms - min_ms) / 6.0  # 99.7% das amostras cairão dentro do intervalo
    delay_ms = random.gauss(mu, sigma)
    delay_ms = max(min_ms, min(delay_ms, max_ms))
    return round(delay_ms / 1000.0, 3)


def schedule_with_delay(base_seconds: float, std_dev: float, min_sec: float, max_sec: float) -> float:
    """Retorna o timestamp absoluto (time.monotonic()) em que uma tarefa deve ser executada."""
    delay = get_human_delay(base_seconds, std_dev, min_sec, max_sec)
    return time.monotonic() + delay
