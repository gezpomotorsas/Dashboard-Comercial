from app.services.deal_analytics.stage_semantics import resolve_commercial_stage_group


def test_cotizacion_financiera_group():
    key, label, order = resolve_commercial_stage_group("Cotización y simulación financiera")
    assert key == "cotizacion_financiera"
    assert "Cotización" in label
    assert order == 20


def test_venta_pedido_group():
    key, _, _ = resolve_commercial_stage_group("Pedido y separación")
    assert key == "venta_pedido"


def test_cierre_ganado_group():
    key, _, _ = resolve_commercial_stage_group("Cierre ganado vehículo entregado")
    assert key == "cierre_ganado"


def test_same_semantics_across_brands():
    voyah, _, _ = resolve_commercial_stage_group("Estudio de crédito o leasing")
    mhero, _, _ = resolve_commercial_stage_group("Estudio de crédito o leasing")
    assert voyah == mhero == "cotizacion_financiera"
