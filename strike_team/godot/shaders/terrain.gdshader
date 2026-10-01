shader_type spatial;
// Terrain: biome ground texture on flat parts, triplanar rock on slopes, snow above snow_height.
// Two-scale sampling + macro variation hide texture tiling on the big mountain faces.

uniform sampler2D ground_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D ground_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D ground_rough : hint_roughness_g, filter_linear_mipmap, repeat_enable;
uniform sampler2D rock_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rock_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D top_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D top_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec3 ground_tint : source_color = vec3(1.0);
uniform vec3 rock_tint : source_color = vec3(1.0);
uniform float ground_tile = 4.0;       // metres per texture repeat
uniform float rock_tile = 14.0;
uniform float snow_height = 9999.0;

varying vec3 wpos;
varying vec3 wnrm;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

vec4 tri(sampler2D t, vec3 p, vec3 n, float tile) {
	vec3 w = pow(abs(n), vec3(4.0));
	w /= (w.x + w.y + w.z);
	return texture(t, p.zy / tile) * w.x + texture(t, p.xz / tile) * w.y + texture(t, p.xy / tile) * w.z;
}

void fragment() {
	vec2 uv = wpos.xz / ground_tile;
	float macro = texture(ground_albedo, wpos.xz / 97.0).g;
	vec3 g = mix(texture(ground_albedo, uv).rgb, texture(ground_albedo, uv * 0.27 + 0.31).rgb, 0.35);
	g *= ground_tint * mix(0.78, 1.18, macro);
	vec3 gn = texture(ground_normal, uv).rgb;
	float gr = texture(ground_rough, uv).g;

	vec3 r = tri(rock_albedo, wpos, wnrm, rock_tile).rgb;
	r = mix(r, tri(rock_albedo, wpos, wnrm, rock_tile * 4.3).rgb, 0.4) * rock_tint;
	vec3 rn = tri(rock_normal, wpos, wnrm, rock_tile).rgb;

	float slope = 1.0 - wnrm.y;
	float noise = texture(rock_albedo, wpos.xz / 41.0).r;
	float rw = smoothstep(0.16, 0.34, slope + (noise - 0.5) * 0.18);
	float sw = smoothstep(snow_height, snow_height + 14.0, wpos.y + noise * 18.0) * (1.0 - smoothstep(0.45, 0.7, slope));

	vec3 s = texture(top_albedo, wpos.xz / 6.0).rgb;
	vec3 sn = texture(top_normal, wpos.xz / 6.0).rgb;

	ALBEDO = mix(mix(g, r, rw), s, sw);
	NORMAL_MAP = mix(mix(gn, rn, rw), sn, sw);
	ROUGHNESS = mix(mix(gr, 0.85, rw), 0.55, sw);
	// far-away terrain picks up a little haze colour from the albedo, fog does the rest
}
