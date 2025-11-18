import cv2
import asyncio
import json
import base64
import time
from typing import Dict, Set
import logging
from fastapi import WebSocket
from ultralytics import YOLO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class YOLOProcessor:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(YOLOProcessor, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.active_streams = {}
        self.connected_clients = {}
        self.stream_tasks = {}
        self.model = YOLO("yolov8n.pt")
        self._initialized = True
        logger.info("✅ YOLOv8n cargado (Instancia única)")
        


    async def start_yolo_stream(self, stream_id: str, rtsp_url: str):
        if stream_id in self.active_streams:
            logger.info(f"✅ YOLO stream {stream_id} ya está activo")
            return True
            
        logger.info(f"🚀 Iniciando YOLO stream para {stream_id}...")
        logger.info(f"📡 Conectando a RTSP: {rtsp_url}")
        
        self.active_streams[stream_id] = True
        self.connected_clients[stream_id] = set()
        
        task = asyncio.create_task(self._process_rtsp_stream(stream_id, rtsp_url))
        self.stream_tasks[stream_id] = task
        
        logger.info(f"✅ YOLO processing INICIADO para {stream_id}")
        return True
    


    async def _process_rtsp_stream(self, stream_id: str, rtsp_url: str):

        cap = cv2.VideoCapture(rtsp_url)
        
        if not cap.isOpened():
            logger.error(f"No se pudo abrir RTSP: {rtsp_url}")
            self.active_streams[stream_id] = False
            return
            
        try:
            while self.active_streams.get(stream_id, False):
                ret, frame = cap.read()
                if not ret:
                    await asyncio.sleep(1)
                    continue
                                
                                
                # 🔥 OPTIMIZACIÓN: Resolución MUY BAJA para máximo rendimiento
                height, width = frame.shape[:2]

                # Reducir a 240p (426x240) - MÁS PEQUEÑO
                target_height = 240  # En lugar de 480
                scale = target_height / height
                target_width = int(width * scale)

                # Limitar ancho máximo para mantener aspecto 16:9
                if target_width > 426:  # Aspect ratio para 240p
                    target_width = 426
                    target_height = int(height * (426 / width))

                frame_resized = cv2.resize(frame, (target_width, target_height))
                #logger.info(f"📐 Resolución OPTIMIZADA: {target_width}x{target_height}")
                
                # Procesar con YOLO
                results = self.model(frame_resized, verbose=False)
                annotated_frame = results[0].plot()
                
                # Obtener detecciones
                detections = []
                for result in results:
                    boxes = result.boxes
                    if boxes is not None:
                        for box in boxes:
                            cls_id = int(box.cls[0])
                            conf = float(box.conf[0])
                            # Ajustar bbox a resolución original
                            x1, y1, x2, y2 = box.xyxy[0].tolist()
                            detections.append({
                                "class": self.model.names[cls_id],
                                "confidence": round(conf, 2),
                                "bbox": [x1, y1, x2, y2]
                            })
                
                # 🔥 MEJOR CALIDAD para compensar resolución baja
                encode_params = [
                    cv2.IMWRITE_JPEG_QUALITY, 80,  # Subir calidad
                    cv2.IMWRITE_JPEG_OPTIMIZE, 1
                ]
                
                # Convertir frame
                success, buffer = cv2.imencode('.jpg', annotated_frame, encode_params)
                if not success:
                    logger.error("Error encoding frame")
                    continue
                    
                jpg_as_text = base64.b64encode(buffer).decode('utf-8')
                
                message = {
                    "stream_id": stream_id,
                    "image": jpg_as_text,
                    "detections": detections,
                    "timestamp": time.time(),
                    "resolution": f"{target_width}x{target_height}"
                }
                
                if self.connected_clients[stream_id]:
                    await self._broadcast_to_clients(stream_id, message)
                    
                # 🔥 OPTIMIZACIÓN: Mantener 4 FPS
                await asyncio.sleep(0.25)  # 4 FPS
                
        except Exception as e:
            logger.error(f"Error en stream {stream_id}: {e}")
        finally:
            cap.release()
            self.active_streams[stream_id] = False
    



    
    async def _broadcast_to_clients(self, stream_id: str, message: dict):
        message_json = json.dumps(message)
        clients = self.connected_clients[stream_id].copy()
        
        for client in clients:
            try:
                await client.send_text(message_json)
            except Exception:
                self.connected_clients[stream_id].discard(client)
    
    async def add_websocket_client(self, stream_id: str, websocket: WebSocket):
        if stream_id not in self.connected_clients:
            self.connected_clients[stream_id] = set()
        self.connected_clients[stream_id].add(websocket)
    
    async def remove_websocket_client(self, stream_id: str, websocket: WebSocket):
        if stream_id in self.connected_clients:
            self.connected_clients[stream_id].discard(websocket)
    
    async def stop_yolo_stream(self, stream_id: str):
        if stream_id in self.active_streams:
            self.active_streams[stream_id] = False
            
        if stream_id in self.stream_tasks:
            self.stream_tasks[stream_id].cancel()
            try:
                await self.stream_tasks[stream_id]
            except asyncio.CancelledError:
                pass
            del self.stream_tasks[stream_id]
    
    def is_yolo_stream_active(self, stream_id: str) -> bool:
        """Verifica si un stream YOLO está activo y funcionando"""
        # Verificar que esté marcado como activo
        if not self.active_streams.get(stream_id, False):
            logger.info(f"❌ {stream_id} no está en active_streams")
            return False
        
        # Verificar que el task esté corriendo
        if stream_id not in self.stream_tasks:
            logger.info(f"❌ {stream_id} no está en stream_tasks")
            return False
        
        task = self.stream_tasks[stream_id]
        if task.done():
            logger.info(f"❌ {stream_id} task está terminado")
            # Si el task terminó, limpiar
            if stream_id in self.active_streams:
                self.active_streams[stream_id] = False
            return False
        
        logger.info(f"✅ {stream_id} está ACTIVO y funcionando")
        return True






yolo_processor = YOLOProcessor()