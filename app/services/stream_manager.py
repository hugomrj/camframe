import subprocess

class StreamManager:
    def __init__(self):
        self.processes = {}

    def start_stream(self, video_id: int, file_path: str):
        if video_id in self.processes:
            return

        rtsp_url = f"rtsp://localhost:8554/video{video_id}"

        cmd = [
            "ffmpeg",
            "-re",
            "-stream_loop", "-1",   # ← LOOP infinito
            "-i", file_path,
            "-c", "copy",
            "-f", "rtsp",
            rtsp_url
        ]

        p = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        self.processes[video_id] = p


        

    def stop_stream(self, video_id: int):
        if video_id in self.processes:
            self.processes[video_id].terminate()
            del self.processes[video_id]


    def is_running(self, video_id: int) -> bool:
        return video_id in self.processes and self.processes[video_id].poll() is None




STREAMER = StreamManager()
