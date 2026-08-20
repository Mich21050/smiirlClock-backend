# Smiirl custom backend
I recently acuiqred a smiirl clock for cheap. By default its completly dependent on the vendors cloud. Using Wireshark I reverse engineered the cloud API and built a simple fastapi based backend for it.
All you need to do is to set your dns server to resolve api.smiirl.com to your local server ip and start up the docker container. It also includes a simple webui. 
