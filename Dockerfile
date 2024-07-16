FROM ubuntu:22.04 as build_base
LABEL maintainer="Shaadow Technology SL"
LABEL purpose='Lambda-readMark'

ENV DEBIAN_FRONTEND="noninteractive" TZ="Europe/London"
RUN apt update && apt install -y \
    python3-dev python3-pip python3-numpy python-is-python3 \
    libjpeg-dev libgif-dev libtiff5-dev libpng-dev poppler-utils \
    git gcovr lcov ttf-mscorefonts-installer fonts-cantarell \
    lmodern fonts-aenigma fonts-georgewilliams ttf-bitstream-vera \
    ttf-sjfonts fonts-unifont fonts-entypo fonts-isabella \
    fonts-mplus fonts-prociono ttf-anonymous-pro ttf-engadget \
    ttf-staypuft ttf-summersby \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHON_INCLUDE=/usr/include/python3.10

# ---------------------------
FROM build_base as build_deps

RUN apt update && apt install -y zip wget

# Download cmake version 3.28
WORKDIR /workspace/deps/
RUN wget https://github.com/Kitware/CMake/releases/download/v3.28.1/cmake-3.28.1-linux-x86_64.tar.gz
RUN tar -xzvf cmake-3.28.1-linux-x86_64.tar.gz
RUN cd cmake-3.28.1-linux-x86_64
RUN ln -s /workspace/deps/cmake-3.28.1-linux-x86_64/bin/cmake /usr/bin/cmake

# Download deps
RUN mkdir -p /workspace/deps/opencv
WORKDIR /workspace/deps/opencv
RUN wget https://github.com/opencv/opencv/archive/4.8.0.zip
RUN unzip 4.8.0.zip

RUN mkdir -p /workspace/deps/opencv_contrib
WORKDIR /workspace/deps/opencv_contrib
RUN wget https://github.com/opencv/opencv_contrib/archive/4.8.0.zip
RUN unzip 4.8.0.zip

RUN mkdir -p /workspace/deps/libboost
WORKDIR /workspace/deps/libboost
RUN wget https://boostorg.jfrog.io/artifactory/main/release/1.79.0/source/boost_1_79_0.tar.bz2

RUN mkdir -p /workspace/deps/onnxruntime
WORKDIR /workspace/deps/onnxruntime
RUN wget https://github.com/microsoft/onnxruntime/releases/download/v1.8.0/onnxruntime-linux-x64-1.8.0.tgz
RUN mv onnxruntime-linux-x64-1.8.0.tgz onnxruntime.tgz

RUN mkdir -p /workspace/deps/leptonica
WORKDIR /workspace/deps/leptonica
RUN wget https://github.com/DanBloomberg/leptonica/releases/download/1.83.1/leptonica-1.83.1.tar.gz

RUN mkdir -p /workspace/deps/tesseract
WORKDIR /workspace/deps/tesseract
RUN wget https://github.com/tesseract-ocr/tesseract/archive/5.3.2.zip
RUN unzip 5.3.2.zip

RUN mkdir -p /workspace/deps/cryptopp-pem
WORKDIR /workspace/deps/cryptopp-pem
RUN wget https://github.com/noloader/cryptopp-pem/archive/refs/tags/CRYPTOPP_8_2_0.zip
RUN unzip CRYPTOPP_8_2_0.zip

RUN mkdir -p /workspace/deps/cryptopp
WORKDIR /workspace/deps/cryptopp
RUN wget https://github.com/weidai11/cryptopp/archive/refs/tags/CRYPTOPP_8_7_0.zip
RUN unzip CRYPTOPP_8_7_0.zip

RUN mkdir -p /workspace/deps/licensepp
WORKDIR /workspace/deps/licensepp
RUN wget https://github.com/abumq/licensepp/archive/refs/tags/v1.0.6.zip
RUN unzip v1.0.6.zip

RUN mkdir -p /workspace/deps/freetype
WORKDIR /workspace/deps/freetype
RUN wget https://download.savannah.gnu.org/releases/freetype/freetype-2.13.0.tar.gz
RUN tar --strip-components=1 -xvzf freetype-2.13.0.tar.gz && rm freetype-2.13.0.tar.gz

#Compile OpenCV
RUN mkdir /workspace/deps/opencv/opencv-4.8.0/build
WORKDIR /workspace/deps/opencv/opencv-4.8.0/build
RUN cmake -D CMAKE_BUILD_TYPE=RELEASE -D OPENCV_EXTRA_MODULES_PATH=/workspace/deps/opencv_contrib/opencv_contrib-4.8.0/modules  -D BUILD_EXAMPLES=ON ..
RUN make -j4
RUN make install
RUN make DESTDIR=/workspace/install install

# Compile Boost
WORKDIR /workspace/deps/libboost
RUN tar --bzip2 -xf boost_1_79_0.tar.bz2
WORKDIR /workspace/deps/libboost/boost_1_79_0
RUN ./bootstrap.sh --prefix=/workspace/install/libboost && ./b2 install

# Set Onnxruntime
WORKDIR /workspace/deps/onnxruntime
RUN tar xvzf onnxruntime.tgz && rm onnxruntime.tgz
RUN mv onnxruntime-linux-x64-1.8.0 /workspace/install/

# Compile leptonica
WORKDIR /workspace/deps/leptonica
RUN tar -xf leptonica-1.83.1.tar.gz
RUN mkdir /workspace/deps/leptonica/leptonica-1.83.1/build
WORKDIR /workspace/deps/leptonica/leptonica-1.83.1/build
RUN cmake -DBUILD_SHARED_LIBS=ON ..
RUN make -j4
RUN make install
RUN make DESTDIR=/workspace/install install

# Compile tesseract
RUN mkdir /workspace/deps/tesseract/tesseract-5.3.2/build
WORKDIR /workspace/deps/tesseract/tesseract-5.3.2/build
RUN cmake -DLeptonica_DIR=/workspace/deps/leptonica/leptonica-1.83.1/build/ -DBUILD_SHARED_LIBS=1 -DBUILD_TRAINING_TOOLS=0 ..
RUN make -j4
RUN make install
RUN make DESTDIR=/workspace/install install

# Compile FreeType
RUN mkdir /workspace/deps/freetype/build
WORKDIR /workspace/deps/freetype/build
RUN cmake -D BUILD_SHARED_LIBS=true -D CMAKE_BUILD_TYPE=Release ..
RUN make -j4
RUN make install
RUN make DESTDIR=/workspace/install install

# install Crypto++
WORKDIR /workspace/deps/
RUN cp cryptopp-pem/cryptopp-pem-CRYPTOPP_8_2_0/* cryptopp/cryptopp-CRYPTOPP_8_7_0/
WORKDIR cryptopp/cryptopp-CRYPTOPP_8_7_0/
RUN make
RUN make install
RUN make DESTDIR=/workspace/install install

# Compile licensepp
RUN mkdir /workspace/deps/licensepp/licensepp-1.0.6/build
WORKDIR /workspace/deps/licensepp/licensepp-1.0.6/build
RUN cmake ..
RUN make
RUN make DESTDIR=/workspace/install install

# ----------------------------
FROM build_base as final_image
COPY --from=build_deps /workspace/install/usr/ /usr/
COPY --from=build_deps /usr/local/share/opencv4 /usr/local/share/
COPY --from=build_deps /workspace/install/libboost/ /usr/

COPY --from=build_deps /workspace/install/onnxruntime-linux-x64-1.8.0/ /usr/local/lib/onnxruntime-linux-x64-1.8.0
ENV ONNX_RUNTIME_PATH /usr/local/lib/onnxruntime-linux-x64-1.8.0

RUN ldconfig

COPY tessdata /app/tessdata/
ENV TESSDATA_PREFIX=/app/tessdata

COPY font_metrics /app/font_metrics
ENV FONT_METRICS_PATH=/app/font_metrics

RUN cd /usr/local/bin \ && ln -s /usr/bin/python3 python
COPY libs /usr/lib/

COPY scripts /app
COPY configs app/configs

COPY requirements.txt /tmp/
RUN pip3 install -r /tmp/requirements.txt
RUN pip3 install --target /app awslambdaric

#cambiar estas dos lineas con cada entrega de shaadow
COPY shadow-5.0.9-cp310-cp310-linux_x86_64.whl /tmp/
RUN pip3 install /tmp/shadow-5.0.9-cp310-cp310-linux_x86_64.whl

RUN pip install torch  
RUN pip install torchvision
RUN pip install pillow
RUN pip install pdf2image
WORKDIR /app/
ENTRYPOINT ["/usr/local/bin/python", "-m", "awslambdaric"]
CMD ["app.handler"]