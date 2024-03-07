FROM ubuntu:20.04

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update && apt-get -y upgrade && \
    apt-get -y install python3.8 && \
    apt update && apt install python3-pip -y

# Method1 - installing LibreOffice and java
RUN apt-get install -y libreoffice
RUN apt-get install -y aspell-ru
RUN apt-get install -y libenchant1c2a

# Method2 - additionally installing unoconv
RUN apt-get install unoconv

ARG CACHEBUST=1

# copying input doc/docx files to the docker's linux
COPY requirements.txt .

RUN pip install -r requirements.txt