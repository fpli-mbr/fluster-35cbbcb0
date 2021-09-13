import { MP4Demuxer } from "./mp4_demuxer.js";
var verboseLog = true;

console.log = (function () {
    var console_log = console.log;
    var timeStart = new Date().getTime();

    return function () {
        if (!verboseLog) {
            return;
        }
        var delta = new Date().getTime() - timeStart;
        var args = [];
        args.push((delta / 1000).toFixed(2) + ':');
        for (var i = 0; i < arguments.length; i++) {
            args.push(arguments[i]);
        }
        console_log.apply(console, args);
    };
})();

function guid() {
    let s4 = () => {
        return Math.floor((1 + Math.random()) * 0x10000)
            .toString(16)
            .substring(1);
    }
    return s4() + s4() + '-' + s4() + '-' + s4() + '-' + s4() + '-' + s4() + s4() + s4();
}

class Frame {
    constructor(imageData, position) {
        this.imageData = imageData;
        this.percents = 0;
        this.position = position;
    }

    getBuffer() {
        return this.imageData;
    }

    getSize() {
        return this.imageData.length;
    }

    getMatch() {
        return this.percents;
    }

    getPosition() {
        return this.position;
    }

    getStatics(imageDataTarget) {
        let counter = 0;
        this.imageData.every(function (v, i) {
            if (Math.abs(v - imageDataTarget[i]) != 0) {
                counter++
            }
            return true;
        })
        this.percents = 100 - Math.round(counter * 100 / this.imageData.length);
    }

}

class ClientTest {
    constructor(contextType, canvas) {
        this.contextType = contextType //Options webgl or 2d

        // If the canvas is null, we create one offscreen.
        this.canvas = (canvas == null) ? new OffscreenCanvas(10, 10) : canvas;

        // Depending on the type of context we will create a texture or not
        if (this.contextType == 'webgl' || this.contextType == 'webgl2') {
            this.ctx = this.canvas.getContext(this.contextType);
            this.texture = this.ctx.createTexture();
        } else {
            this.ctx = this.canvas.getContext(this.contextType);
            this.texture = null;
        }

        // It is unique and identifies the client in the connections to the server.
        this.guid = guid();
        // It's true if the video decoded is using hardware acceleration.
        this.hardware_acceleration = false;
        // It's the width of the frame video decoded.
        this.width = 0;
        // It's the height of the frame video decoded.
        this.height = 0;
        // It contains the decoded frames.
        this.frames = []
    }

    async postToServer(url_server, fields) {
        let formData = new FormData();

        // We fill the form with the proper fields
        fields.forEach(element => {
            formData.append(element[0], element[1]);
        });

        // We send the request with the form info and wait for the answer.
        let response = await fetch(url_server, { method: "POST", body: formData });
        if (!response.ok) {
            throw Error(`Server returned ${response.status}: ${response.statusText}`);
        }
        return response;
    }

    async getFromServer(url_server) {
        // We send the request with the form info and wait for the answer.
        let response = await fetch(url_server);
        if (!response.ok) {
            throw Error(`Server returned ${response.status}: ${response.statusText}`);
        }
        return response;
    }

    yuvToVideFrame(yuv420p) {
        let uStart = this.width * this.height;
        let vStart = uStart + Math.floor(uStart / 4);
        let stride = Math.floor(this.width / 2);

        let planes = [
            { stride: this.width, offset: 0 },
            { stride: stride, offset: uStart },
            { stride: stride, offset: vStart }
        ];

        let options = {
            format: 'I420',
            codedWidth: this.width,
            codedHeight: this.height,
            timestamp: 0,
            colorSpace: {
                fullRange: false,
                matrix: "bt709",
                primaries: "bt709",
                transfer: "bt709"
            },
            layout: planes
        }

        return new VideoFrame(yuv420p, options);;
    }

    convertToRGBA(yuv420p) {
        let frame = this.yuvToVideFrame(yuv420p);
        let canvas = new OffscreenCanvas(this.width, this.height);
        let ctx = canvas.getContext(this.contextType);
        let data = null;
        if (this.contextType == '2d') {
            data = this.onFrame2D(frame, ctx);
        } else {
            data = this.onFrameWebGL(frame, ctx);
        }
        return data;
    }

    frameToArrayGL(gl, frame, texture) {
        // We draw an image in a texture and transform it into a buffer.
        let width = this.width;
        let height = this.height;
        let framebuffer = gl.createFramebuffer();
        let data = new Uint8Array(width * height * 4);

        gl.bindTexture(gl.TEXTURE_2D, texture);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, frame);
        gl.viewport(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight);
        gl.bindFramebuffer(gl.FRAMEBUFFER, framebuffer);
        gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, texture, 0);
        gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, data);

        return data;
    }

    onFrameWebGL(frame, ctx) {
        // We create a buffer with the image using WebGL context to canvas and store it into a Frame class
        let data = this.frameToArrayGL(ctx, frame, this.texture);
        frame.close();
        return data;
    };

    onFrame2D(frame, ctx) {
        // We create a buffer with the image using 2d context to canvas and store it into a Frame class
        ctx.drawImage(frame, 0, 0, this.width, this.height);
        frame.close();
        let imageData = ctx.getImageData(0, 0, this.width, this.height);
        return imageData.data;
    }


    async play(url_coded_file) {
        // We transfer the value of this to the anonymous output function using this trick.
        let client = this;
        // We create an object that can request and decode de input file.
        let demuxer = new MP4Demuxer(url_coded_file);

        // We assign a dictionary with the render and error function
        let init = {
            output: function (frame) {
                // Only by using a software video decoder can we access a decoded frame in I420 format.
                client.hardware_acceleration = (frame.planes != null);
                // It depends on the type of context that we get the buffer differently.
                let data = null;
                if (client.contextType == '2d') {
                    data = client.onFrame2D(frame, client.ctx);
                } else {
                    data = client.onFrameWebGL(frame, client.ctx);
                }
                client.frames.push(new Frame(data, client.frames.length));
            },
            error: e => console.error("We have a issue", e),
        };

        // We create de video decoder
        let decoder = new VideoDecoder(init);

        // We create a promise of play the video
        return new Promise(function (resolve, reject) {
            demuxer.getConfig().then((config) => {
                // Overwrite the colorSpace
                config.colorSpace = {
                    fullRange: false,
                    matrix: "bt709",
                    primaries: "bt709",
                    transfer: "bt709"
                };
                // We get the information about the video settings.
                decoder.configure(config);
                client.width = client.canvas.width = config.codedWidth;
                client.height = client.canvas.height = config.codedHeight;
                // We start to send h264 frames to the decoder
                demuxer.start((chunk) => { decoder.decode(chunk); })
                // We make sure that everything has been sent and reproduced
                decoder.flush().then(() => {
                    resolve(client);
                });
            });
        });
    }
}


async function runTestForFile(canvas) {

    // We create the client to connect to the server to avoid Chromium's sandbox
    let client = new ClientTest('2d', canvas);

    // Start of the process
    console.log(`Test started for identifier ${client.guid}`);

    // We send a request using a predefined name to retrieve the encoded file that we want to test
    let response = await client.postToServer("/coded_file_to_test.html", [["guid", client.guid]]);

    // We play the video
    response = await client.play(response.headers.get('coded_file'));

    // We check if the decoded frame matches the decoded one that the server has.
    let promises = []
    client.frames.forEach(function (frame) {
        promises.push(new Promise(function (resolve, reject) {
            let url_frame = "/decoded_frame.html?" + new URLSearchParams({
                guid: client.guid,
                frame: frame.getPosition(),
                width: client.width,
                height: client.height
            })

            let promise = client.getFromServer(url_frame);

            promise.then((response) => {
                response.arrayBuffer().then((buffer) => {
                    let yuv420p = new Uint8Array(buffer);
                    frame.getStatics(client.convertToRGBA(yuv420p));
                    resolve(frame);
                })
            });
        }));
    })

    // Wait for all the frames
    let totalFrames = 0;
    let framesWithErrors = 0;
    await Promise.allSettled(promises).then((results) => {
        totalFrames = results.length;
        results.forEach(result => {
            if (result.value.getMatch() < 100) {
                framesWithErrors++;
            }
        });
        console.log("total frame ", totalFrames, " with errors ", framesWithErrors);
    });

    // We request the clean of the intermediate files.
    response = client.postToServer("/clean_intermediate_files.html",
        [
            ["guid", client.guid],
            ["frames", totalFrames],
            ["errors", framesWithErrors],
        ]);

    // End of the process
    console.log(`Test finished for identifier ${client.guid}`);
}

export { runTestForFile };
