from ultralytics import YOLO
import cv2

model = YOLO("yolo26n.pt")  # load YOLO26 model
model.train(data="/Users/anusha/Desktop/unibots-yolo-demo1/Ball Detection.v1i.yolo26/data.yaml", epochs=100) # train on merged dataset for 100 epochs
model = YOLO("runs/detect/train/weights/best.pt") 

# start webcam
cap = cv2.VideoCapture(0)
cap.set(3, 640)
cap.set(4, 480)


# Loop through the video frames
while cap.isOpened():
    # Read a frame from the video
    success, frame = cap.read()

    if success:
        # Run YOLO26 tracking on the frame, persisting tracks between frames
        results = model.track(frame, persist=True)

        # Visualize the results on the frame
        annotated_frame = results[0].plot()

        # Display the annotated frame
        cv2.imshow("YOLO26 Tracking", annotated_frame)

        # Break the loop if ESC is pressed
        if cv2.waitKey(1) & 0xFF == 27:
            break
    else:
        # Break the loop if the end of the video is reached
        break

# Release the video capture object and close the display window
cap.release()
cv2.destroyAllWindows()
