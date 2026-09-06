#!/usr/bin/env python3
"""Fix cover loading in 3D library template - improve error handling and robustness"""

import re
import os

template_path = os.path.join(os.path.dirname(__file__), 'templates', 'biblioteca_de_jogos_3d_definitiva.html')

with open(template_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern for old loadGameCover function
pattern = r'function loadGameCover\(gameObject\) \{[\s\S]*?gameObject\.userData\.coverRequested = false;[\s\S]*?// Don\'t retry automatically.*?\n\s*\}'

replacement = '''function loadGameCover(gameObject) {
            const game = gameObject.userData.game;
            const material = gameObject.userData.frontMaterial;
            if (!game.coverUrl || gameObject.userData.coverRequested || !material) return;
            
            gameObject.userData.coverRequested = true;
            
            textureLoader.load(
                game.coverUrl,
                (texture) => {
                    if (!material) return;
                    texture.colorSpace = THREE.SRGBColorSpace;
                    material.map = texture;
                    material.needsUpdate = true;
                    gameObject.userData.coverLoaded = true;
                },
                undefined,
                (error) => {
                        console.warn(`[GameUnexa 3D] Cover load failed for "${game.title}": ${game.coverUrl}`);
                    gameObject.userData.coverRequested = false;
                    gameObject.userData.coverFailed = true;
                }
            );
        }'''

if re.search(pattern, content, re.DOTALL):
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    print('✓ Updated loadGameCover function')
else:
    print('✗ Could not find loadGameCover pattern - will try manual approach')
    # Try simpler pattern
    if 'gameObject.userData.coverRequested = false;' in content:
        # Find and replace just the error handler
        content = content.replace(
            '// Don\'t retry automatically; user can refresh if needed\n            });',
            '// Error handled, allow retry later\n            });'
        )
        print('✓ Updated error handling comment')

# Add improved cover queue management before the createGameObject function
cover_queue_code = '''
        // Cover loading queue to prevent overwhelming the network
        const coverLoadQueue = {
            queue: [],
            loading: 0,
            maxConcurrent: 3,
            
            async enqueue(gameObject) {
                if (this.loading < this.maxConcurrent) {
                    this.loading++;
                    try {
                        await this.loadWithTimeout(gameObject);
                    } finally {
                        this.loading--;
                        if (this.queue.length > 0) {
                            const nextGame = this.queue.shift();
                            this.enqueue(nextGame);
                        }
                    }
                } else {
                    this.queue.push(gameObject);
                }
            },
            
            loadWithTimeout(gameObject) {
                return new Promise((resolve) => {
                    const timeout = setTimeout(() => {
                            console.warn(`[GameUnexa 3D] Cover load timeout for "${gameObject.userData.game.title}"`);
                        resolve();
                    }, 6000);
                    
                    const game = gameObject.userData.game;
                    const material = gameObject.userData.frontMaterial;
                    
                    textureLoader.load(
                        game.coverUrl,
                        (texture) => {
                            clearTimeout(timeout);
                            if (material) {
                                texture.colorSpace = THREE.SRGBColorSpace;
                                material.map = texture;
                                material.needsUpdate = true;
                            }
                            resolve();
                        },
                        undefined,
                        () => {
                            clearTimeout(timeout);
                            console.warn(`[GameUnexa 3D] Failed to load: ${game.coverUrl}`);
                            resolve();
                        }
                    );
                });
            }
        };
'''

# Find a good insertion point (before createGameObject or similar)
if 'function createGameObject' in content and 'const coverLoadQueue' not in content:
    insert_pos = content.find('function createGameObject')
    content = content[:insert_pos] + cover_queue_code + '\n        ' + content[insert_pos:]
    print('✓ Added cover loading queue management')

# Save improved version
with open(template_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('✓ Cover loading improvements applied successfully')
