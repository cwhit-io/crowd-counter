"""Image processing with YOLO inference and clustering."""
import logging
import os
import cv2
import numpy as np
from sklearn.cluster import DBSCAN
from ultralytics import YOLO
from .config import Config, PresetConfig


logger = logging.getLogger(__name__)


def process_image_worker(image_queue, result_queue, model_path, output_dir, 
                        infer_conf, infer_iou, cluster_eps, min_cluster_size):
    """
    Worker function to process images:
    - Runs YOLO inference
    - Clusters detections
    - Annotates images
    - Sends results to result_queue
    """
    logger.info("Starting image processing worker")
    
    while True:
        image_path = image_queue.get()
        if image_path is None:
            logger.info("Worker received stop signal")
            break
        
        try:
            logger.info(f"Processing image: {image_path}")
            model = YOLO(model_path)

            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"Failed to load image: {image_path}")
                result_queue.put({
                    "preset": os.path.basename(image_path),
                    "count": 0,
                    "error": "Failed to load image"
                })
                continue

            # Run inference
            results = model.predict(img, conf=infer_conf, iou=infer_iou, verbose=False)
            boxes = (
                results[0].boxes.xyxy.cpu().numpy()
                if len(results[0].boxes) > 0
                else np.array([])
            )

            # Cluster & count
            count = 0
            if len(boxes) > 0:
                centers = np.array([(box[0] + box[2]) / 2 for box in boxes])
                if len(centers) >= min_cluster_size:
                    clustering = DBSCAN(
                        eps=cluster_eps,
                        min_samples=min_cluster_size
                    ).fit(centers.reshape(-1, 1))
                    count = len(set(clustering.labels_)) - (1 if -1 in clustering.labels_ else 0)
                else:
                    count = len(centers)

            # Draw boxes & count
            annotated_img = img.copy()
            for box in boxes:
                x1, y1, x2, y2 = map(int, box[:4])
                cv2.rectangle(annotated_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    annotated_img,
                    "Person",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2
                )
            cv2.putText(
                annotated_img,
                f"Count: {count}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                2
            )

            # Extract preset number and name from filename
            filename = os.path.basename(image_path)
            name_part = filename.removeprefix("preset_").rsplit(".", 1)[0]
            preset_num, preset_name_safe = name_part.split("_", 1)
            
            # Build output filename
            annotated_filename = f"{preset_name_safe}_{preset_num}.jpg"
            annotated_path = os.path.join(
                output_dir,
                "annotated_images",
                annotated_filename
            )
            os.makedirs(os.path.dirname(annotated_path), exist_ok=True)
            cv2.imwrite(
                annotated_path,
                annotated_img,
                [int(cv2.IMWRITE_JPEG_QUALITY), 70]
            )
            logger.info(
                f"Saved annotated image to {annotated_path}, Count: {count}"
            )

            # Push result
            result_queue.put({
                "preset": preset_num,
                "name": preset_name_safe.replace("_", " "),
                "count": count,
                "annotated_path": annotated_path
            })

        except Exception as e:
            logger.error(f"Error processing {image_path}: {str(e)}")
            result_queue.put({
                "preset": os.path.basename(image_path),
                "count": 0,
                "error": str(e)
            })


def start_processing_workers(num_workers, image_queue, result_queue, 
                            model_path, output_dir, infer_conf, infer_iou,
                            cluster_eps, min_cluster_size):
    """
    Start worker processes for image processing.
    
    Returns:
        list: List of worker Process objects
    """
    from multiprocessing import Process
    
    workers = []
    logger.info(f"Starting {num_workers} image processing workers")
    
    for _ in range(num_workers):
        p = Process(
            target=process_image_worker,
            args=(image_queue, result_queue, model_path, output_dir,
                  infer_conf, infer_iou, cluster_eps, min_cluster_size)
        )
        p.start()
        workers.append(p)
    
    return workers


def stop_workers(workers, image_queue, num_workers):
    """Send stop signals and wait for workers to complete."""
    logger.info("Sending stop signals to workers")
    for _ in range(num_workers):
        image_queue.put(None)
    
    for w in workers:
        w.join()
    logger.info("All processing workers have completed")


def collect_results(result_queue):
    """Collect all results from the result queue."""
    results = []
    while not result_queue.empty():
        results.append(result_queue.get())
    return results
