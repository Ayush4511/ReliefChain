/* ═══════════════════════════════════════════════════════════
   RELIEFCHAIN — CINEMATIC 3D SCROLL ENGINE
   Three.js + GSAP ScrollTrigger
   5 Scenes: Disaster → Action → Blockchain → Impact → CTA
   ═══════════════════════════════════════════════════════════ */

(function () {
    'use strict';

    // ─── CORE SETUP ───
    const canvas = document.getElementById('cinematic-canvas');
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.8;

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x0a0a1a, 0.035);

    const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 200);
    camera.position.set(0, 2, 10);

    const clock = new THREE.Clock();

    // ─── GLOBAL STATE ───
    let scrollProgress = 0;    // 0 → 1
    let currentScene = 0;      // 0-4
    let mouseX = 0, mouseY = 0;

    // ─── RESIZE ───
    window.addEventListener('resize', () => {
        const w = window.innerWidth, h = window.innerHeight;
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
    });

    // ─── MOUSE PARALLAX ───
    window.addEventListener('mousemove', (e) => {
        mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
        mouseY = (e.clientY / window.innerHeight - 0.5) * 2;
    });

    // ═══════════════════════════════════════
    // SCENE 1: DISASTER — Destroyed city, rain, cold lighting
    // ═══════════════════════════════════════
    const disasterGroup = new THREE.Group();
    scene.add(disasterGroup);

    // Ground plane
    const groundGeo = new THREE.PlaneGeometry(100, 100);
    const groundMat = new THREE.MeshStandardMaterial({ color: 0x1a1a2e, roughness: 0.9 });
    const ground = new THREE.Mesh(groundGeo, groundMat);
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.5;
    ground.receiveShadow = true;
    disasterGroup.add(ground);

    // Destroyed buildings (procedural boxes)
    const buildingMat = new THREE.MeshStandardMaterial({ color: 0x2a2a3e, roughness: 0.8, metalness: 0.1 });
    const buildings = [];
    for (let i = 0; i < 18; i++) {
        const w = 0.8 + Math.random() * 1.5;
        const h = 1 + Math.random() * 4;
        const d = 0.8 + Math.random() * 1.5;
        const geo = new THREE.BoxGeometry(w, h, d);
        const mesh = new THREE.Mesh(geo, buildingMat.clone());
        mesh.material.color.setHSL(0.65, 0.1, 0.1 + Math.random() * 0.1);
        mesh.position.set(
            (Math.random() - 0.5) * 30,
            h / 2 - 0.5,
            (Math.random() - 0.5) * 20 - 5
        );
        mesh.rotation.y = Math.random() * 0.3;
        // Tilt some for "destroyed" effect
        mesh.rotation.z = (Math.random() - 0.5) * 0.15;
        mesh.rotation.x = (Math.random() - 0.5) * 0.08;
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        disasterGroup.add(mesh);
        buildings.push(mesh);
    }

    // Rubble (small boxes scattered)
    for (let i = 0; i < 40; i++) {
        const s = 0.1 + Math.random() * 0.4;
        const geo = new THREE.BoxGeometry(s, s * 0.5, s);
        const mat = new THREE.MeshStandardMaterial({ color: 0x3a3a4e, roughness: 0.95 });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.set(
            (Math.random() - 0.5) * 25,
            s * 0.25 - 0.4,
            (Math.random() - 0.5) * 15
        );
        mesh.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, 0);
        disasterGroup.add(mesh);
    }

    // ── Rain Particle System ──
    const rainCount = 3000;
    const rainGeo = new THREE.BufferGeometry();
    const rainPositions = new Float32Array(rainCount * 3);
    const rainVelocities = new Float32Array(rainCount);
    for (let i = 0; i < rainCount; i++) {
        rainPositions[i * 3] = (Math.random() - 0.5) * 40;
        rainPositions[i * 3 + 1] = Math.random() * 20;
        rainPositions[i * 3 + 2] = (Math.random() - 0.5) * 40;
        rainVelocities[i] = 0.15 + Math.random() * 0.2;
    }
    rainGeo.setAttribute('position', new THREE.BufferAttribute(rainPositions, 3));
    const rainMat = new THREE.PointsMaterial({
        color: 0x8899bb,
        size: 0.06,
        transparent: true,
        opacity: 0.6,
        depthWrite: false
    });
    const rain = new THREE.Points(rainGeo, rainMat);
    disasterGroup.add(rain);

    // ── Disaster Lights ──
    const coldLight = new THREE.DirectionalLight(0x4466aa, 0.6);
    coldLight.position.set(-5, 8, 5);
    coldLight.castShadow = true;
    coldLight.shadow.mapSize.set(1024, 1024);
    scene.add(coldLight);

    const ambientCold = new THREE.AmbientLight(0x1a2040, 0.4);
    scene.add(ambientCold);

    // Lightning flash light (hidden by default)
    const flashLight = new THREE.PointLight(0xeeeeff, 0, 50);
    flashLight.position.set(0, 10, 0);
    scene.add(flashLight);

    // ═══════════════════════════════════════
    // SCENE 3: BLOCKCHAIN — Glowing node network
    // ═══════════════════════════════════════
    const blockchainGroup = new THREE.Group();
    blockchainGroup.visible = false;
    scene.add(blockchainGroup);

    const nodePositions = [
        new THREE.Vector3(0, 0, 0),
        new THREE.Vector3(-4, 2, -3),
        new THREE.Vector3(3, 3, -2),
        new THREE.Vector3(-3, -1, -5),
        new THREE.Vector3(5, -1, -4),
        new THREE.Vector3(-2, 4, -1),
        new THREE.Vector3(4, 1, -6),
        new THREE.Vector3(-5, 0, -3),
        new THREE.Vector3(1, -2, -5),
        new THREE.Vector3(2, 5, -3),
    ];
    const nodeLabels = ['Donor', 'NGO', 'Volunteer', 'Supplier', 'Hospital', 'Verified', 'Relief', 'Logistics', 'Community', 'Trust'];

    // Create glowing nodes
    const nodes = [];
    const nodeMat = new THREE.MeshBasicMaterial({ color: 0x00f0ff });
    nodePositions.forEach((pos, i) => {
        // Core sphere
        const geo = new THREE.SphereGeometry(0.2, 16, 16);
        const mesh = new THREE.Mesh(geo, nodeMat.clone());
        mesh.position.copy(pos);
        blockchainGroup.add(mesh);

        // Outer glow sphere
        const glowGeo = new THREE.SphereGeometry(0.45, 16, 16);
        const glowMat = new THREE.MeshBasicMaterial({
            color: i % 2 === 0 ? 0x00f0ff : 0xa855f7,
            transparent: true,
            opacity: 0.15,
            depthWrite: false
        });
        const glow = new THREE.Mesh(glowGeo, glowMat);
        glow.position.copy(pos);
        blockchainGroup.add(glow);

        nodes.push({ mesh, glow, label: nodeLabels[i], baseScale: 1 });
    });

    // Connection lines
    const connections = [
        [0, 1], [0, 2], [1, 3], [2, 4], [1, 5], [3, 7], [4, 6],
        [5, 9], [6, 8], [7, 8], [2, 5], [0, 4], [3, 8], [6, 9]
    ];
    const lineMat = new THREE.LineBasicMaterial({ color: 0x00f0ff, transparent: true, opacity: 0.25 });
    connections.forEach(([a, b]) => {
        const geo = new THREE.BufferGeometry().setFromPoints([nodePositions[a], nodePositions[b]]);
        const line = new THREE.Line(geo, lineMat.clone());
        blockchainGroup.add(line);
    });

    // ── Energy particles flowing along connections ──
    const energyCount = 200;
    const energyGeo = new THREE.BufferGeometry();
    const energyPositions = new Float32Array(energyCount * 3);
    const energyProgress = new Float32Array(energyCount);    // 0→1 along path
    const energyConnIdx = new Uint8Array(energyCount);       // which connection
    const energySpeeds = new Float32Array(energyCount);

    for (let i = 0; i < energyCount; i++) {
        energyProgress[i] = Math.random();
        energyConnIdx[i] = Math.floor(Math.random() * connections.length);
        energySpeeds[i] = 0.003 + Math.random() * 0.008;
        const ci = energyConnIdx[i];
        const a = nodePositions[connections[ci][0]];
        const b = nodePositions[connections[ci][1]];
        const t = energyProgress[i];
        energyPositions[i * 3] = a.x + (b.x - a.x) * t;
        energyPositions[i * 3 + 1] = a.y + (b.y - a.y) * t;
        energyPositions[i * 3 + 2] = a.z + (b.z - a.z) * t;
    }
    energyGeo.setAttribute('position', new THREE.BufferAttribute(energyPositions, 3));
    const energyMat = new THREE.PointsMaterial({
        color: 0x00f0ff,
        size: 0.08,
        transparent: true,
        opacity: 0.9,
        depthWrite: false
    });
    const energyParticles = new THREE.Points(energyGeo, energyMat);
    blockchainGroup.add(energyParticles);

    // Blockchain lights
    const neonLight = new THREE.PointLight(0x00f0ff, 2, 30);
    neonLight.position.set(0, 2, 0);
    blockchainGroup.add(neonLight);
    const purpleLight = new THREE.PointLight(0xa855f7, 1.5, 25);
    purpleLight.position.set(3, -1, -4);
    blockchainGroup.add(purpleLight);

    // ═══════════════════════════════════════
    // SCENE 4: IMPACT — Warm, restored world
    // ═══════════════════════════════════════
    const impactGroup = new THREE.Group();
    impactGroup.visible = false;
    scene.add(impactGroup);

    // Warm light particles (fireflies / hope particles)
    const hopeCount = 500;
    const hopeGeo = new THREE.BufferGeometry();
    const hopePos = new Float32Array(hopeCount * 3);
    const hopePhases = new Float32Array(hopeCount);
    for (let i = 0; i < hopeCount; i++) {
        hopePos[i * 3] = (Math.random() - 0.5) * 30;
        hopePos[i * 3 + 1] = Math.random() * 10;
        hopePos[i * 3 + 2] = (Math.random() - 0.5) * 30;
        hopePhases[i] = Math.random() * Math.PI * 2;
    }
    hopeGeo.setAttribute('position', new THREE.BufferAttribute(hopePos, 3));
    const hopeMat = new THREE.PointsMaterial({
        color: 0xf0c040,
        size: 0.12,
        transparent: true,
        opacity: 0.8,
        depthWrite: false
    });
    const hopeParticles = new THREE.Points(hopeGeo, hopeMat);
    impactGroup.add(hopeParticles);

    const warmLight = new THREE.DirectionalLight(0xffc040, 1.2);
    warmLight.position.set(5, 8, 5);
    impactGroup.add(warmLight);
    const warmAmbient = new THREE.AmbientLight(0x4a3520, 0.6);
    impactGroup.add(warmAmbient);

    // ═══════════════════════════════════════
    // CAMERA POSITIONS PER SCENE
    // ═══════════════════════════════════════
    const cameraKeyframes = [
        { pos: new THREE.Vector3(0, 2.5, 12), lookAt: new THREE.Vector3(0, 1, 0) },       // Disaster
        { pos: new THREE.Vector3(0, 3, 8), lookAt: new THREE.Vector3(0, 2, 0) },          // Action
        { pos: new THREE.Vector3(0, 1, 6), lookAt: new THREE.Vector3(0, 1, -3) },         // Blockchain
        { pos: new THREE.Vector3(0, 3, 10), lookAt: new THREE.Vector3(0, 2, 0) },         // Impact
        { pos: new THREE.Vector3(0, 2, 8), lookAt: new THREE.Vector3(0, 2, 0) },          // CTA
    ];

    // ═══════════════════════════════════════
    // GSAP SCROLL TIMELINE
    // ═══════════════════════════════════════
    gsap.registerPlugin(ScrollTrigger);

    const overlays = {
        disaster: document.getElementById('sceneDisaster'),
        action: document.getElementById('sceneAction'),
        blockchain: document.getElementById('sceneBlockchain'),
        impact: document.getElementById('sceneImpact'),
        cta: document.getElementById('sceneCta'),
    };
    const progressBar = document.getElementById('cinProgress');
    const scrollHint = document.getElementById('scrollHint');

    // Main scroll-driven timeline
    ScrollTrigger.create({
        trigger: '#scrollContainer',
        start: 'top top',
        end: 'bottom bottom',
        scrub: 0.5,
        onUpdate: (self) => {
            scrollProgress = self.progress;
            updateScenes(scrollProgress);
        }
    });

    function updateScenes(p) {
        // Update progress bar
        progressBar.style.width = (p * 100) + '%';

        // Fade scroll hint
        if (scrollHint) scrollHint.style.opacity = Math.max(0, 1 - p * 8);

        // Fade in footer during CTA scene
        if (cinFooter) cinFooter.style.opacity = Math.max(0, (p - 0.85) / 0.15);

        // ─── SCENE MAPPING ───
        const sceneRanges = [
            { start: 0, end: 0.2, key: 'disaster', idx: 0 },
            { start: 0.2, end: 0.4, key: 'action', idx: 1 },
            { start: 0.4, end: 0.65, key: 'blockchain', idx: 2 },
            { start: 0.65, end: 0.85, key: 'impact', idx: 3 },
            { start: 0.85, end: 1.0, key: 'cta', idx: 4 },
        ];

        let activeIdx = 0;
        sceneRanges.forEach((r, i) => {
            const overlay = overlays[r.key];
            const localP = Math.max(0, Math.min(1, (p - r.start) / (r.end - r.start)));

            // Fade in at 10-30% of scene, fade out at 70-90%
            let overlayOpacity = 0;
            if (localP > 0.05 && localP < 0.95) {
                const fadeIn = Math.min(1, (localP - 0.05) / 0.2);
                const fadeOut = Math.min(1, (0.95 - localP) / 0.2);
                overlayOpacity = Math.min(fadeIn, fadeOut);
            }
            overlay.style.opacity = overlayOpacity;
            overlay.style.pointerEvents = overlayOpacity > 0.1 ? 'auto' : 'none';

            if (p >= r.start && p < r.end) activeIdx = i;
        });
        if (p >= 0.85) activeIdx = 4;
        currentScene = activeIdx;

        // ─── 3D SCENE VISIBILITY ───
        disasterGroup.visible = (p < 0.45);
        blockchainGroup.visible = (p > 0.35 && p < 0.75);
        impactGroup.visible = (p > 0.55);

        // ─── FOG TRANSITION ───
        if (p < 0.3) {
            scene.fog.color.setHex(0x0a0a1a);
            scene.fog.density = 0.035 - p * 0.05;
            renderer.toneMappingExposure = 0.5 + p * 1.5;
        } else if (p < 0.65) {
            scene.fog.color.setHex(0x050510);
            scene.fog.density = 0.015;
            renderer.toneMappingExposure = 1.0;
        } else {
            scene.fog.color.lerp(new THREE.Color(0x1a1510), (p - 0.65) / 0.35);
            scene.fog.density = 0.02;
            renderer.toneMappingExposure = 1.0 + (p - 0.65) * 2;
        }

        // ─── CAMERA INTERPOLATION ───
        const camFrom = cameraKeyframes[activeIdx];
        const camTo = cameraKeyframes[Math.min(activeIdx + 1, 4)];
        const range = sceneRanges[activeIdx];
        const localP2 = Math.max(0, Math.min(1, (p - range.start) / (range.end - range.start)));
        const eased = smoothstep(localP2);

        camera.position.lerpVectors(camFrom.pos, camTo.pos, eased);
        const lookTarget = new THREE.Vector3().lerpVectors(camFrom.lookAt, camTo.lookAt, eased);

        // Mouse parallax offset
        camera.position.x += mouseX * 0.3;
        camera.position.y += mouseY * 0.15;
        camera.lookAt(lookTarget);

        // ─── LIGHTING TRANSITIONS ───
        coldLight.intensity = Math.max(0, 1 - p * 3);
        ambientCold.intensity = Math.max(0, 0.4 - p * 1);

        // ─── RAIN INTENSITY ───
        rainMat.opacity = Math.max(0, 0.6 - p * 2.5);
    }

    function smoothstep(t) {
        return t * t * (3 - 2 * t);
    }

    // ═══════════════════════════════════════
    // ANIMATION LOOP
    // ═══════════════════════════════════════
    let lastFlash = 0;

    function animate() {
        requestAnimationFrame(animate);
        const dt = clock.getDelta();
        const elapsed = clock.getElapsedTime();

        // ── Rain animation ──
        if (disasterGroup.visible) {
            const pos = rain.geometry.attributes.position;
            for (let i = 0; i < rainCount; i++) {
                pos.array[i * 3 + 1] -= rainVelocities[i];
                if (pos.array[i * 3 + 1] < -1) {
                    pos.array[i * 3 + 1] = 15 + Math.random() * 5;
                    pos.array[i * 3] = (Math.random() - 0.5) * 40;
                    pos.array[i * 3 + 2] = (Math.random() - 0.5) * 40;
                }
            }
            pos.needsUpdate = true;

            // Lightning flash
            if (scrollProgress < 0.2 && elapsed - lastFlash > 4 + Math.random() * 6) {
                flashLight.intensity = 3;
                lastFlash = elapsed;
                setTimeout(() => { flashLight.intensity = 0; }, 80);
                setTimeout(() => { flashLight.intensity = 1.5; }, 150);
                setTimeout(() => { flashLight.intensity = 0; }, 200);
            }

            // Subtle building sway
            buildings.forEach((b, i) => {
                b.rotation.z = Math.sin(elapsed * 0.3 + i) * 0.01;
            });
        }

        // ── Blockchain energy particles ──
        if (blockchainGroup.visible) {
            const epos = energyParticles.geometry.attributes.position;
            for (let i = 0; i < energyCount; i++) {
                energyProgress[i] += energySpeeds[i];
                if (energyProgress[i] > 1) {
                    energyProgress[i] = 0;
                    energyConnIdx[i] = Math.floor(Math.random() * connections.length);
                }
                const ci = energyConnIdx[i];
                const a = nodePositions[connections[ci][0]];
                const b = nodePositions[connections[ci][1]];
                const t = energyProgress[i];
                epos.array[i * 3] = a.x + (b.x - a.x) * t;
                epos.array[i * 3 + 1] = a.y + (b.y - a.y) * t;
                epos.array[i * 3 + 2] = a.z + (b.z - a.z) * t;
            }
            epos.needsUpdate = true;

            // Node pulse
            nodes.forEach((n, i) => {
                const pulse = 1 + Math.sin(elapsed * 2 + i * 0.7) * 0.15;
                n.mesh.scale.setScalar(pulse);
                n.glow.scale.setScalar(pulse * 1.3);
                n.glow.material.opacity = 0.1 + Math.sin(elapsed * 1.5 + i) * 0.08;
            });

            // Rotate network slowly
            blockchainGroup.rotation.y = elapsed * 0.05;
        }

        // ── Impact particles (fireflies) ──
        if (impactGroup.visible) {
            const hpos = hopeParticles.geometry.attributes.position;
            for (let i = 0; i < hopeCount; i++) {
                hpos.array[i * 3] += Math.sin(elapsed * 0.5 + hopePhases[i]) * 0.005;
                hpos.array[i * 3 + 1] += Math.sin(elapsed * 0.8 + hopePhases[i] * 2) * 0.003;
                hpos.array[i * 3 + 2] += Math.cos(elapsed * 0.4 + hopePhases[i]) * 0.005;
            }
            hpos.needsUpdate = true;
            hopeMat.opacity = 0.5 + Math.sin(elapsed * 1.2) * 0.3;
        }

        renderer.render(scene, camera);
    }

    // ─── INITIAL OVERLAY ANIMATION ───
    window.addEventListener('load', () => {
        // Fade in Scene 1 text
        const h1 = document.querySelector('.scene-disaster h1');
        const p1 = document.querySelector('.scene-disaster p');
        if (h1) gsap.to(h1, { opacity: 1, y: 0, duration: 2, delay: 0.5, ease: 'power2.out' });
        if (p1) gsap.to(p1, { opacity: 1, y: 0, duration: 2, delay: 1.2, ease: 'power2.out' });

        // Show first overlay
        overlays.disaster.style.opacity = 1;
    });

    // ─── PHONE BUTTON INTERACTION ───
    const phoneBtn = document.getElementById('phoneBtn');
    if (phoneBtn) {
        phoneBtn.addEventListener('click', () => {
            phoneBtn.textContent = '✅ Donated!';
            phoneBtn.style.background = 'linear-gradient(135deg, #2d6a4f, #40916c)';
            setTimeout(() => {
                phoneBtn.textContent = 'Donate Securely →';
                phoneBtn.style.background = '';
            }, 2000);
        });
    }

    // ─── START ───
    animate();

})();
