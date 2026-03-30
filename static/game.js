// Flappy Bird-style game using the generated sprite
(function () {
    var canvas = document.getElementById("game-canvas");
    var ctx = canvas.getContext("2d");
    var overlay = document.getElementById("game-overlay");
    var playBtn = document.getElementById("play-btn");
    var scoreDisplay = document.getElementById("score-display");

    var W = canvas.width;
    var H = canvas.height;

    var spriteImg = null;
    var running = false;
    var animFrame = null;

    // Game state
    var bird, pipes, score, frameCount, groundY;

    // Constants
    var GRAVITY = 0.35;
    var FLAP_POWER = -6;
    var PIPE_SPEED = 2;
    var PIPE_GAP = 130;
    var PIPE_WIDTH = 50;
    var PIPE_SPAWN_INTERVAL = 100;
    var BIRD_SIZE = 36;
    var GROUND_HEIGHT = 60;

    groundY = H - GROUND_HEIGHT;

    function reset() {
        bird = { x: 80, y: H / 2 - 20, vy: 0, rotation: 0 };
        pipes = [];
        score = 0;
        frameCount = 0;
        scoreDisplay.textContent = "Score: 0";
    }

    function flap() {
        if (!running) return;
        bird.vy = FLAP_POWER;
    }

    function spawnPipe() {
        var minTop = 60;
        var maxTop = groundY - PIPE_GAP - 60;
        var topHeight = minTop + Math.random() * (maxTop - minTop);
        pipes.push({
            x: W,
            topH: topHeight,
            scored: false
        });
    }

    function update() {
        frameCount++;

        // Bird physics
        bird.vy += GRAVITY;
        bird.y += bird.vy;
        bird.rotation = Math.min(bird.vy * 3, 70);

        // Spawn pipes
        if (frameCount % PIPE_SPAWN_INTERVAL === 0) {
            spawnPipe();
        }

        // Move pipes
        for (var i = pipes.length - 1; i >= 0; i--) {
            pipes[i].x -= PIPE_SPEED;

            // Score
            if (!pipes[i].scored && pipes[i].x + PIPE_WIDTH < bird.x) {
                pipes[i].scored = true;
                score++;
                scoreDisplay.textContent = "Score: " + score;
            }

            // Remove off-screen
            if (pipes[i].x + PIPE_WIDTH < 0) {
                pipes.splice(i, 1);
            }
        }

        // Collision detection
        var bx = bird.x - BIRD_SIZE / 2;
        var by = bird.y - BIRD_SIZE / 2;
        var bw = BIRD_SIZE;
        var bh = BIRD_SIZE;

        // Ground / ceiling
        if (bird.y + BIRD_SIZE / 2 > groundY || bird.y - BIRD_SIZE / 2 < 0) {
            gameOver();
            return;
        }

        // Pipes
        for (var i = 0; i < pipes.length; i++) {
            var p = pipes[i];
            // Top pipe
            if (rectsOverlap(bx, by, bw, bh, p.x, 0, PIPE_WIDTH, p.topH)) {
                gameOver();
                return;
            }
            // Bottom pipe
            var bottomY = p.topH + PIPE_GAP;
            if (rectsOverlap(bx, by, bw, bh, p.x, bottomY, PIPE_WIDTH, groundY - bottomY)) {
                gameOver();
                return;
            }
        }
    }

    function rectsOverlap(x1, y1, w1, h1, x2, y2, w2, h2) {
        return x1 < x2 + w2 && x1 + w1 > x2 && y1 < y2 + h2 && y1 + h1 > y2;
    }

    function draw() {
        // Sky
        ctx.fillStyle = "#87CEEB";
        ctx.fillRect(0, 0, W, H);

        // Clouds (simple)
        ctx.fillStyle = "rgba(255,255,255,0.7)";
        drawCloud(50, 60, 40);
        drawCloud(180, 100, 30);
        drawCloud(280, 40, 35);

        // Pipes
        for (var i = 0; i < pipes.length; i++) {
            var p = pipes[i];
            // Top pipe
            ctx.fillStyle = "#4CAF50";
            ctx.fillRect(p.x, 0, PIPE_WIDTH, p.topH);
            ctx.fillStyle = "#388E3C";
            ctx.fillRect(p.x - 3, p.topH - 20, PIPE_WIDTH + 6, 20);

            // Bottom pipe
            var bottomY = p.topH + PIPE_GAP;
            ctx.fillStyle = "#4CAF50";
            ctx.fillRect(p.x, bottomY, PIPE_WIDTH, groundY - bottomY);
            ctx.fillStyle = "#388E3C";
            ctx.fillRect(p.x - 3, bottomY, PIPE_WIDTH + 6, 20);
        }

        // Ground
        ctx.fillStyle = "#8B4513";
        ctx.fillRect(0, groundY, W, GROUND_HEIGHT);
        ctx.fillStyle = "#228B22";
        ctx.fillRect(0, groundY, W, 10);

        // Bird (sprite)
        ctx.save();
        ctx.translate(bird.x, bird.y);
        ctx.rotate(bird.rotation * Math.PI / 180);
        if (spriteImg) {
            ctx.drawImage(spriteImg, -BIRD_SIZE / 2, -BIRD_SIZE / 2, BIRD_SIZE, BIRD_SIZE);
        } else {
            ctx.fillStyle = "#FFD600";
            ctx.fillRect(-BIRD_SIZE / 2, -BIRD_SIZE / 2, BIRD_SIZE, BIRD_SIZE);
        }
        ctx.restore();

        // Score on canvas
        ctx.fillStyle = "#fff";
        ctx.strokeStyle = "#333";
        ctx.lineWidth = 3;
        ctx.font = "bold 28px 'Press Start 2P', monospace";
        ctx.textAlign = "center";
        ctx.strokeText(score, W / 2, 50);
        ctx.fillText(score, W / 2, 50);
    }

    function drawCloud(x, y, r) {
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.arc(x + r, y - r * 0.3, r * 0.7, 0, Math.PI * 2);
        ctx.arc(x + r * 1.5, y, r * 0.8, 0, Math.PI * 2);
        ctx.fill();
    }

    function gameLoop() {
        update();
        draw();
        animFrame = requestAnimationFrame(gameLoop);
    }

    function gameOver() {
        running = false;
        cancelAnimationFrame(animFrame);
        playBtn.textContent = "\uD83D\uDD04 Play Again!";
        overlay.hidden = false;

        // Draw game over text
        ctx.fillStyle = "rgba(0,0,0,0.4)";
        ctx.fillRect(0, 0, W, H);
        ctx.fillStyle = "#fff";
        ctx.font = "bold 18px 'Press Start 2P', monospace";
        ctx.textAlign = "center";
        ctx.fillText("Game Over!", W / 2, H / 2 - 10);
        ctx.font = "12px 'Press Start 2P', monospace";
        ctx.fillText("Score: " + score, W / 2, H / 2 + 20);
    }

    function startGame() {
        reset();
        overlay.hidden = true;
        running = true;
        gameLoop();
    }

    // Set sprite from the main app
    window.setGameSprite = function (imgSrc) {
        var img = new Image();
        img.onload = function () {
            spriteImg = img;
            // Draw idle preview
            drawIdleScreen();
        };
        img.src = imgSrc;
    };

    function drawIdleScreen() {
        ctx.fillStyle = "#87CEEB";
        ctx.fillRect(0, 0, W, H);
        ctx.fillStyle = "rgba(255,255,255,0.7)";
        drawCloud(50, 60, 40);
        drawCloud(180, 100, 30);
        drawCloud(280, 40, 35);
        ctx.fillStyle = "#8B4513";
        ctx.fillRect(0, groundY, W, GROUND_HEIGHT);
        ctx.fillStyle = "#228B22";
        ctx.fillRect(0, groundY, W, 10);

        // Draw sprite in center
        if (spriteImg) {
            ctx.drawImage(spriteImg, W / 2 - 24, H / 2 - 24, 48, 48);
        }
    }

    // Controls
    playBtn.addEventListener("click", startGame);

    canvas.addEventListener("click", function () {
        if (running) flap();
    });

    document.addEventListener("keydown", function (e) {
        if (e.code === "Space" && running) {
            e.preventDefault();
            flap();
        }
    });

    // Touch support for mobile
    canvas.addEventListener("touchstart", function (e) {
        if (running) {
            e.preventDefault();
            flap();
        }
    });

    // Draw initial empty screen
    drawIdleScreen();
})();
