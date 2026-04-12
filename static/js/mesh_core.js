let video, canvas, ctx;
let expectedHoles = 8;
let brightnessThreshold = 170;
let minHoleArea = 300;

function startCamera() {
  video = document.getElementById('video');
  canvas = document.getElementById('canvas');
  ctx = canvas.getContext('2d');

  navigator.mediaDevices.getUserMedia({
    video: { facingMode: "environment" }
  }).then(stream => {
    video.srcObject = stream;
  });
}

function inspectNow() {
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;

  ctx.drawImage(video, 0, 0);

  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const data = imageData.data;

  const W = canvas.width;
  const H = canvas.height;

  const cx = W / 2;
  const cy = H / 2;
  const radius = Math.min(W, H) * 0.35;

  const binary = new Uint8Array(W * H);

  // Threshold + ROI
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const dist = Math.sqrt((x - cx) ** 2 + (y - cy) ** 2);
      if (dist > radius) continue;

      const i = (y * W + x) * 4;
      const gray = 0.299 * data[i] + 0.587 * data[i+1] + 0.114 * data[i+2];

      binary[y * W + x] = gray > brightnessThreshold ? 1 : 0;
    }
  }

  const visited = new Uint8Array(W * H);
  let holes = 0;

  function floodFill(x, y) {
    const queue = [[x, y]];
    let size = 0;

    while (queue.length) {
      const [cx2, cy2] = queue.shift();
      const idx = cy2 * W + cx2;

      if (visited[idx]) continue;
      visited[idx] = 1;

      if (binary[idx] !== 1) continue;

      size++;

      [[1,0],[-1,0],[0,1],[0,-1]].forEach(([dx,dy])=>{
        const nx = cx2 + dx;
        const ny = cy2 + dy;

        if(nx>=0 && ny>=0 && nx<W && ny<H){
          queue.push([nx,ny]);
        }
      });
    }

    return size;
  }

  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const idx = y * W + x;

      if (!visited[idx] && binary[idx] === 1) {
        const size = floodFill(x, y);

        if (size >= minHoleArea) {
          holes++;
        }
      }
    }
  }

  const result = holes >= expectedHoles ? "PASS" : "FAIL";

  document.getElementById("result").innerText =
    `Holes: ${holes} | Result: ${result}`;
}