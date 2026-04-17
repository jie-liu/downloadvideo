import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch, MagicMock
from downloader import get_info

MOCK_INFO = {
    "title": "Test Video",
    "formats": [
        {"format_id": "137", "resolution": "1920x1080", "ext": "mp4",
         "filesize": 500_000_000, "filesize_approx": None, "width": 1920, "height": 1080},
        {"format_id": "22", "resolution": "1280x720", "ext": "mp4",
         "filesize": 200_000_000, "filesize_approx": None, "width": 1280, "height": 720},
        {"format_id": "18", "resolution": "640x360", "ext": "mp4",
         "filesize": None, "filesize_approx": 50_000_000, "width": 640, "height": 360},
        {"format_id": "audio", "resolution": "audio only", "ext": "m4a",
         "filesize": None, "filesize_approx": None, "width": None, "height": None},
    ]
}

def test_get_info_returns_title_and_formats(mocker):
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = MOCK_INFO
    mocker.patch("downloader.yt_dlp.YoutubeDL", return_value=mock_ydl)

    result = get_info("https://example.com/video")

    assert result["title"] == "Test Video"
    assert len(result["formats"]) == 4

def test_get_info_formats_sorted_by_size_desc(mocker):
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = MOCK_INFO
    mocker.patch("downloader.yt_dlp.YoutubeDL", return_value=mock_ydl)

    result = get_info("https://example.com/video")
    formats = result["formats"]

    # 第一个应该是最大的（500MB）
    assert formats[0]["format_id"] == "137"
    # 第二个是 200MB
    assert formats[1]["format_id"] == "22"
    # filesize_approx 排在有 filesize 的后面
    assert formats[2]["format_id"] == "18"
    # 两者都为 None 的排末尾
    assert formats[3]["format_id"] == "audio"

def test_get_info_display_size_human_readable(mocker):
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = MOCK_INFO
    mocker.patch("downloader.yt_dlp.YoutubeDL", return_value=mock_ydl)

    result = get_info("https://example.com/video")
    # 500MB 格式应有可读大小
    assert "MB" in result["formats"][0]["display_size"] or "GB" in result["formats"][0]["display_size"]
    # 无大小的应显示 Unknown
    assert result["formats"][3]["display_size"] == "Unknown"
