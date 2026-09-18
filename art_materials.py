"""JPGFLY visual material and palette vocabulary.

These are deterministic rendering/style primitives selected by the Fly Brain.
They expand the physical language available to existing brain decisions.
"""
from __future__ import annotations

EXTRA_PALETTE_PRESETS={
    "ACID_CANDY":("#ff2bd6","#d7ff00","#00f0ff","#ff8a00","#3a00ff","#111111"),
    "ELECTRIC_BLUEPRINT":("#07131f","#00d9ff","#45fff2","#5b7cff","#d7fbff","#101820"),
    "CHROME_NIGHT":("#0b0d10","#38414d","#8ba0b8","#dce7f2","#6b36ff","#ff3cac"),
    "VOID_GOLD":("#090807","#2a2117","#7e5b24","#c99538","#f2d790","#d8d1c5"),
    "HOSPITAL_MOLD":("#edf0dc","#bacaa1","#6f8f65","#334a3b","#c9b57b","#171b18"),
    "SUNBURN_DREAM":("#ff5b3a","#ff9b68","#ffd0a8","#7d4f88","#34203d","#f2dfd3"),
    "INFRARED_MEAT":("#17070b","#6e1028","#c52b48","#ff5e62","#ff9a72","#d9b7a7"),
    "LASER_MOSS":("#07120b","#24ff72","#a8ff2a","#00d9a6","#5a6b27","#111111"),
    "PLASMA_SUGAR":("#12091f","#ff4dff","#8f5bff","#20e3ff","#ffcb52","#f7f1ff"),
    "UV_BRUISE":("#100a18","#2d1852","#6137a7","#a65cff","#ff55c8","#8ea0ff"),
    "CYBER_CERAMIC":("#0f1115","#e8edf2","#a8b7c7","#5de0e6","#3d67ff","#ff4f9a"),
    "RADIOACTIVE_ROSE":("#151006","#ff3864","#ff78ad","#d7ff2f","#65ffb5","#0c0c0c"),
}

MATERIAL_BRUSHES=("neon_glow","impasto_heavy","chrome_ribbon","airbrush_fog","marker_bleed","oil_lump")
MATERIAL_TECHNIQUES=("neon_bloom","impasto_ridge","chrome_layer","airbrush_bloom","ink_bleed")

PALETTE_STYLE={
    "TOXIC_NEON":("NEON","neon_glow",.26),
    "FUNERAL_NEON":("NEON","neon_glow",.22),
    "NIGHT_CANDY":("NEON","neon_glow",.18),
    "ACID_CANDY":("NEON","neon_glow",.30),
    "ELECTRIC_BLUEPRINT":("NEON","neon_glow",.23),
    "LASER_MOSS":("NEON","neon_glow",.28),
    "PLASMA_SUGAR":("NEON","neon_glow",.27),
    "UV_BRUISE":("NEON","neon_glow",.20),
    "RADIOACTIVE_ROSE":("NEON","neon_glow",.25),
    "CHROME_NIGHT":("CHROME","chrome_ribbon",.34),
    "CYBER_CERAMIC":("CHROME","chrome_ribbon",.26),
    "VOID_GOLD":("IMPASTO","impasto_heavy",.38),
    "INFRARED_MEAT":("IMPASTO","oil_lump",.42),
    "SUNBURN_DREAM":("IMPASTO","oil_lump",.30),
    "HOSPITAL_MOLD":("BLEED","marker_bleed",.20),
    "MOLDY_CANDY":("BLEED","marker_bleed",.18),
    "BRUISED_PASTEL":("AIRBRUSH","airbrush_fog",.14),
    "INSECT_WING":("AIRBRUSH","airbrush_fog",.12),
}

def palette_style(palette_name:str)->dict:
    effect,material,depth=PALETTE_STYLE.get(str(palette_name or "").upper(),("MATTE","ink_line",.08))
    return {"render_effect":effect,"material_style":material,"paint_depth":float(depth)}
