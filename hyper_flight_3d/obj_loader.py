import os
import pygame
from OpenGL.GL import *

class OBJModel:
    """
    Wavefront .OBJ 3D Model Loader and Renderer for OpenGL.
    Parses vertices (v), texture coords (vt), normals (vn), and faces (f).
    Compiles models into fast OpenGL Display Lists.
    """
    def __init__(self, filepath, color=(0.8, 0.8, 0.9), scale=1.0):
        self.filepath = filepath
        self.vertices = []
        self.normals = []
        self.texcoords = []
        self.faces = []
        self.display_list = None
        self.color = color
        self.scale = scale

        if os.path.exists(filepath):
            self.load_obj(filepath)
            self.compile_display_list()

    def load_obj(self, filename):
        with open(filename, 'r') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                values = line.split()
                if not values:
                    continue

                if values[0] == 'v':
                    v = list(map(float, values[1:4]))
                    self.vertices.append([v[0]*self.scale, v[1]*self.scale, v[2]*self.scale])
                elif values[0] == 'vn':
                    vn = list(map(float, values[1:4]))
                    self.normals.append(vn)
                elif values[0] == 'vt':
                    vt = list(map(float, values[1:3]))
                    self.texcoords.append(vt)
                elif values[0] == 'f':
                    face = []
                    tex_indices = []
                    norm_indices = []
                    for v_str in values[1:]:
                        w = v_str.split('/')
                        face.append(int(w[0]) - 1)
                        if len(w) >= 2 and w[1]:
                            tex_indices.append(int(w[1]) - 1)
                        if len(w) >= 3 and w[2]:
                            norm_indices.append(int(w[2]) - 1)
                    self.faces.append((face, tex_indices, norm_indices))

    def compile_display_list(self):
        self.display_list = glGenLists(1)
        glNewList(self.display_list, GL_COMPILE)
        glEnable(GL_LIGHTING)
        glColor3fv(self.color)

        for face, tex_indices, norm_indices in self.faces:
            if len(face) == 3:
                glBegin(GL_TRIANGLES)
            elif len(face) == 4:
                glBegin(GL_QUADS)
            else:
                glBegin(GL_POLYGON)

            for i in range(len(face)):
                if norm_indices and i < len(norm_indices) and norm_indices[i] < len(self.normals):
                    glNormal3fv(self.normals[norm_indices[i]])
                if tex_indices and i < len(tex_indices) and tex_indices[i] < len(self.texcoords):
                    glTexCoord2fv(self.texcoords[tex_indices[i]])
                glVertex3fv(self.vertices[face[i]])
            glEnd()

        glEndList()

    def render(self, pos=(0, 0, 0), rot=(0, 0, 0), override_color=None):
        glPushMatrix()
        glTranslatef(pos[0], pos[1], pos[2])
        if rot[1] != 0: glRotatef(rot[1], 0, 1, 0)
        if rot[0] != 0: glRotatef(rot[0], 1, 0, 0)
        if rot[2] != 0: glRotatef(rot[2], 0, 0, 1)

        if override_color:
            glColor3fv(override_color)

        if self.display_list:
            glCallList(self.display_list)

        glPopMatrix()
