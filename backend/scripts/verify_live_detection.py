import requests

login_resp = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    json={"username": "admin@cleanliness.gov.in", "password": "ChangeMe@Admin2026"},
)
token = login_resp.json().get("access_token")

with open("storage/annotated/ANN-IMG-20260930-9D8523E6.jpg", "rb") as f:
    files = {"file": ("roadside_garbage.jpg", f, "image/jpeg")}
    data = {"confidence_threshold": "0.35", "detection_mode": "solid", "create_incident": "true"}
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post("http://localhost:8000/api/v1/detection/image", files=files, data=data, headers=headers)
    print("HTTP Status:", resp.status_code)
    d = resp.json()
    print("Detections count:", len(d.get("detections", [])))
    for item in d.get("detections", []):
        print(f"  {item['class_name']} ({item['confidence']*100:.1f}%) BBox: {item['bbox']}")
    print("Incident created:", d.get("incident_created"))
    print("Incident IDs:", d.get("incident_ids"))
    print("Annotated Image URL:", d.get("annotated_image_url"))
