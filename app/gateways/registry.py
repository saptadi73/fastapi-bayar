from app.core.config import Settings
from app.core.errors import AppError
from app.gateways.midtrans.client import MidtransSnapClient
from app.gateways.doku.client import DokuDirectClient


def gateway_for_channel(channel_code: str, settings: Settings) -> str:
    code = channel_code.upper()
    if code.startswith("DOKU_"):
        if not settings.doku_enabled:
            raise AppError("GATEWAY_NOT_CONFIGURED", "DOKU belum diaktifkan", 503)
        return "DOKU"
    if code.startswith("MIDTRANS_"):
        if not settings.midtrans_enabled:
            raise AppError("GATEWAY_NOT_CONFIGURED", "Midtrans belum diaktifkan", 503)
        return "MIDTRANS"
    raise AppError("UNSUPPORTED_CHANNEL", "Payment channel tidak didukung", 422, {"channel_code": channel_code})


def client_for_channel(channel_code: str, settings: Settings):
    if channel_code.upper() not in {"MIDTRANS_SNAP", "DOKU_INDOMARET"}:
        raise AppError("UNSUPPORTED_CHANNEL", "Adapter channel belum tersedia", 422)
    gateway = gateway_for_channel(channel_code, settings)
    if gateway == "MIDTRANS":
        if not settings.midtrans_server_key:
            raise AppError("GATEWAY_NOT_CONFIGURED", "MIDTRANS_SERVER_KEY belum dikonfigurasi", 503)
        return MidtransSnapClient(settings)
    if gateway == "DOKU":
        if not settings.doku_client_id or not settings.doku_secret_key:
            raise AppError("GATEWAY_NOT_CONFIGURED", "DOKU_CLIENT_ID/DOKU_SECRET_KEY belum dikonfigurasi", 503)
        return DokuDirectClient(settings)
    raise AppError("GATEWAY_NOT_IMPLEMENTED", "Adapter gateway belum tersedia untuk channel ini", 501)
