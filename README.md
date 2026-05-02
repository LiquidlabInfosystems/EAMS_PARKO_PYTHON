sudo apt update
sudo apt install python3-picamera2 python3-opencv libcamera-apps -y

python3 -m venv env
source env/bin/activate

export PYTHONPATH=/usr/lib/python3/dist-packages