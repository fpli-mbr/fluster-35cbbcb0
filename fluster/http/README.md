We have as resources:

```
  https://github.com/w3c/webcodecs/blob/main/explainer.md
  https://web.dev/webcodecs/
  https://github.com/gpac/mp4box.js
  https://w3c.github.io/media-source/
  https://developer.mozilla.org/en-US/docs/Web/API/HTMLCanvasElement
  https://developer.mozilla.org/en-US/docs/Web/API/MediaStream
  https://developer.mozilla.org/en-US/docs/Web/API/CanvasRenderingContext2D/getImageData
  https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API/Tutorial/Pixel_manipulation_with_canvas
```

- A raw file decoded with the reference decoder in yuv420p
  **ldecod -s -i AUD_MW_E.264 -o AUD_MW_E.yuv**
  **split -b 345600 -d bbb.yuv --additional-suffix=_reference.yuv420 frame_hw_640_360_**
- An mp4 file obtained with FFmpeg from test byte-stream format test vector
  **ffmpeg -i AUD_MW_E.264 -vcodec copy -colorspace smpte170m -color_primaries smpte170m -color_trc smpte170m -color_range pc output_2.mp4**
- A server with a custom GET and POST treatment that serves files and frames from a video in several formats

ffmpeg -y -f rawvideo -s 176x144 -pix_fmt yuv420p -i reference_frame_1.yuv420 -pix_fmt rgba -f rawvideo ffmpeg.rgba

gst-launch-1.0 -v filesrc location=foo.yuv ! rawvideoparse use-sink-caps=false format=i420 width=640 height=360 ! videoconvert ! video/x-raw,format=RGB ! filesink location=foo.rgb

CHROME_VERSION_EXTRA="stable" LD_LIBRARY_PATH="$PWD:/opt/libva/lib" LIBVA_DRIVER_NAME=iHD /opt/google/chrome/chrome --enable-features=VaapiVideoDecoder --ignore-gpu-blocklist --use-gl=desktop --enable-blink-features=WebCodecs

VideoFrame.storage_type is
- STORAGE_OPAQUE in HW
- STORAGE_OWNED_MEMORY in SW


Different tests carried out:

- (1) Chrome asks for MP4 and sends RGBA (3-7% match)
    - Chrome demuxes and decodes it using MP4Box and VideoDecoder from WebCodecs
    - VideoDecoder creates frames (ImageBitmap)
    - Canvas paints the frame
    - We retrieve ImageData that is sent to the server in RGBA format.
    - Server compare with YUV420p frame with 0 as tolerance value, if the tolerance value is increased to 16 the match is around 98%

- (2) Chrome asks for mp4 and sends YUV420p (100% match)
    - Chrome demuxes and decodes it using MP4Box and VideoDecoder from WebCodecs
    - VideoDecoder using software decoder that creates frames (ImageBitmap) and planes
    - Canvas paints the frame
    - We retrieve the planes in YUV420p (i420 in doc) format and send it to the server.
    - Server compare with YUV420p frame with 0 as tolerance value.

- (3) Chrome asks for YUV420p frames and sends an RGBA (100%)
    - Chrome demuxes and decodes it using MP4Box and VideoDecoder from WebCodecs.
    - Receive info about number of frames, width, and height of the video
    - Chrome asks for frames inside a loop.
    - Chrome receives a YUV420p for each request.
    - Chrome converts it to RGBA and paints it.
    - Chrome retrieves ImageData that is sent to the server as RGBA buffer.
    - The server is compared to the equivalent frame decoded by the reference decoder.

- (4) Chrome pide el video en una sucesion de YUV420p
    - Los mete en un VideoFrame los convierte en RGBA y los envia al servidor
    - Chrome pie del MP4 decodifica, pinta y envia el rgba con correccion
      de color al servidor
    - El servidor compara el RGBA generado con VideoFrame con el RGBA decodificado con VideoDecoder
