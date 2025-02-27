##########################################################################
#
#  Copyright (c) 2012, John Haddon. All rights reserved.
#  Copyright (c) 2013-2014, Image Engine Design Inc. All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are
#  met:
#
#      * Redistributions of source code must retain the above
#        copyright notice, this list of conditions and the following
#        disclaimer.
#
#      * Redistributions in binary form must reproduce the above
#        copyright notice, this list of conditions and the following
#        disclaimer in the documentation and/or other materials provided with
#        the distribution.
#
#      * Neither the name of John Haddon nor the names of
#        any other contributors to this software may be used to endorse or
#        promote products derived from this software without specific prior
#        written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
#  IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
#  THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
#  PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
#  CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
#  EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
#  PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
#  PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
#  LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
#  NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
##########################################################################

import math

import imath
import inspect
import time
import unittest

import IECore
import IECoreScene

import Gaffer
import GafferTest
import GafferDispatch
import GafferScene
import GafferSceneTest

class InstancerTest( GafferSceneTest.SceneTestCase ) :

	def test( self ) :

		sphere = IECoreScene.SpherePrimitive()
		instanceInput = GafferSceneTest.CompoundObjectSource()
		instanceInput["in"].setValue(
			IECore.CompoundObject( {
				"bound" : IECore.Box3fData( imath.Box3f( imath.V3f( -2 ), imath.V3f( 2 ) ) ),
				"children" : {
					"sphere" : {
						"object" : sphere,
						"bound" : IECore.Box3fData( sphere.bound() ),
						"transform" : IECore.M44fData( imath.M44f().scale( imath.V3f( 2 ) ) ),
					},
				}
			} )
		)

		seeds = IECoreScene.PointsPrimitive(
			IECore.V3fVectorData(
				[ imath.V3f( 1, 0, 0 ), imath.V3f( 1, 1, 0 ), imath.V3f( 0, 1, 0 ), imath.V3f( 0, 0, 0 ) ]
			)
		)
		seedsInput = GafferSceneTest.CompoundObjectSource()
		seedsInput["in"].setValue(
			IECore.CompoundObject( {
				"bound" : IECore.Box3fData( imath.Box3f( imath.V3f( 1, 0, 0 ), imath.V3f( 2, 1, 0 ) ) ),
				"children" : {
					"seeds" : {
						"bound" : IECore.Box3fData( seeds.bound() ),
						"transform" : IECore.M44fData( imath.M44f().translate( imath.V3f( 1, 0, 0 ) ) ),
						"object" : seeds,
					},
				},
			}, )
		)

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( seedsInput["out"] )
		instancer["prototypes"].setInput( instanceInput["out"] )
		instancer["parent"].setValue( "/seeds" )
		instancer["name"].setValue( "instances" )

		self.assertEqual( instancer["out"].object( "/" ), IECore.NullObject() )
		self.assertEqual( instancer["out"].transform( "/" ), imath.M44f() )
		self.assertEqual( instancer["out"].bound( "/" ), imath.Box3f( imath.V3f( -1, -2, -2 ), imath.V3f( 4, 3, 2 ) ) )
		self.assertEqual( instancer["out"].childNames( "/" ), IECore.InternedStringVectorData( [ "seeds" ] ) )

		self.assertEqual( instancer["out"].object( "/seeds" ), IECore.NullObject() )
		self.assertEqual( instancer["out"].transform( "/seeds" ), imath.M44f().translate( imath.V3f( 1, 0, 0 ) ) )
		self.assertEqual( instancer["out"].bound( "/seeds" ), imath.Box3f( imath.V3f( -2, -2, -2 ), imath.V3f( 3, 3, 2 ) ) )
		self.assertEqual( instancer["out"].childNames( "/seeds" ), IECore.InternedStringVectorData( [ "instances" ] ) )

		self.assertEqual( instancer["out"].object( "/seeds/instances" ), IECore.NullObject() )
		self.assertEqual( instancer["out"].transform( "/seeds/instances" ), imath.M44f() )
		self.assertEqual( instancer["out"].bound( "/seeds/instances" ), imath.Box3f( imath.V3f( -2, -2, -2 ), imath.V3f( 3, 3, 2 ) ) )
		self.assertEqual( instancer["out"].childNames( "/seeds/instances" ), IECore.InternedStringVectorData( [ "sphere" ] ) )

		self.assertEqual( instancer["out"].object( "/seeds/instances/sphere" ), IECore.NullObject() )
		self.assertEqual( instancer["out"].transform( "/seeds/instances/sphere" ), imath.M44f() )
		self.assertEqual( instancer["out"].bound( "/seeds/instances/sphere" ), imath.Box3f( imath.V3f( -2, -2, -2 ), imath.V3f( 3, 3, 2 ) ) )
		self.assertEqual( instancer["out"].childNames( "/seeds/instances/sphere" ), IECore.InternedStringVectorData( [ "0", "1", "2", "3" ] ) )

		for i in range( 0, 4 ) :

			instancePath = "/seeds/instances/sphere/%d" % i

			self.assertEqual( instancer["out"].object( instancePath ), sphere )
			self.assertEqual(
				instancer["out"].transform( instancePath ),
				imath.M44f().scale( imath.V3f( 2 ) ) * imath.M44f().translate( seeds["P"].data[i] )
			)
			self.assertEqual( instancer["out"].bound( instancePath ), sphere.bound() )
			self.assertEqual( instancer["out"].childNames( instancePath ), IECore.InternedStringVectorData() )


		# Test paths that don't exist - the transform will trigger an error, the other functions don't depend on
		# the index, so will just return a reasonable value
		self.assertRaisesRegex(
			Gaffer.ProcessException,
			'Instancer.out.transform : Instance id "77" is invalid, instancer produces only 4 children.  Topology may have changed during shutter.',
			instancer["out"].transform, "/seeds/instances/sphere/77"
		)
		self.assertEqual( instancer["out"].object( "/seeds/instances/sphere/77" ), sphere )
		self.assertEqual( instancer["out"].bound( "/seeds/instances/sphere/77" ), sphere.bound() )
		self.assertEqual( instancer["out"].childNames( "/seeds/instances/sphere/77" ), IECore.InternedStringVectorData() )

		# Test passthrough when disabled
		instancer["enabled"].setValue( False )
		self.assertScenesEqual( instancer["in"], instancer["out"] )
		instancer["enabled"].setValue( True )

		# Test encapsulation options
		encapInstancer = GafferScene.Instancer()
		encapInstancer["in"].setInput( seedsInput["out"] )
		encapInstancer["prototypes"].setInput( instanceInput["out"] )
		encapInstancer["parent"].setValue( "/seeds" )
		encapInstancer["name"].setValue( "instances" )
		encapInstancer["encapsulateInstanceGroups"].setValue( True )

		unencapFilter = GafferScene.PathFilter()
		unencapFilter["paths"].setValue( IECore.StringVectorData( [ "/..." ] ) )

		unencap = GafferScene.Unencapsulate()
		unencap["in"].setInput( encapInstancer["out"] )
		unencap["filter"].setInput( unencapFilter["out"] )

		self.assertTrue( isinstance( encapInstancer["out"].object( "/seeds/instances/sphere/" ), GafferScene.Capsule ) )
		self.assertEqual( encapInstancer["out"].childNames( "/seeds/instances/sphere/" ), IECore.InternedStringVectorData() )
		self.assertScenesEqual( unencap["out"], instancer["out"] )

		# Edit seeds object
		freezeTransform = GafferScene.FreezeTransform()
		freezeTransform["in"].setInput( seedsInput["out"] )
		freezeTransform["filter"].setInput( unencapFilter["out"] )

		instancer["in"].setInput( freezeTransform["out"] )
		encapInstancer["in"].setInput( freezeTransform["out"] )

		self.assertScenesEqual( unencap["out"], instancer["out"] )

		# Then set it back ( to make sure that returning to a previously cached value after
		# changing the seeds doesn't pull an expired Capsule out of the cache )
		freezeTransform["enabled"].setValue( False )
		self.assertScenesEqual( unencap["out"], instancer["out"] )

		# Test passthrough when disabled
		instancer["enabled"].setValue( False )
		self.assertScenesEqual( instancer["in"], instancer["out"] )

	def testThreading( self ) :

		sphere = IECoreScene.SpherePrimitive()
		instanceInput = GafferSceneTest.CompoundObjectSource()
		instanceInput["in"].setValue(
			IECore.CompoundObject( {
				"bound" : IECore.Box3fData( imath.Box3f( imath.V3f( -2 ), imath.V3f( 2 ) ) ),
				"children" : {
					"sphere" : {
						"object" : sphere,
						"bound" : IECore.Box3fData( sphere.bound() ),
						"transform" : IECore.M44fData( imath.M44f().scale( imath.V3f( 2 ) ) ),
					},
				}
			} )
		)

		seeds = IECoreScene.PointsPrimitive(
			IECore.V3fVectorData(
				[ imath.V3f( 1, 0, 0 ), imath.V3f( 1, 1, 0 ), imath.V3f( 0, 1, 0 ), imath.V3f( 0, 0, 0 ) ]
			)
		)
		seedsInput = GafferSceneTest.CompoundObjectSource()
		seedsInput["in"].setValue(
			IECore.CompoundObject( {
				"bound" : IECore.Box3fData( imath.Box3f( imath.V3f( 1, 0, 0 ), imath.V3f( 2, 1, 0 ) ) ),
				"children" : {
					"seeds" : {
						"bound" : IECore.Box3fData( seeds.bound() ),
						"transform" : IECore.M44fData( imath.M44f().translate( imath.V3f( 1, 0, 0 ) ) ),
						"object" : seeds,
					},
				},
			}, )
		)

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( seedsInput["out"] )
		instancer["prototypes"].setInput( instanceInput["out"] )
		instancer["parent"].setValue( "/seeds" )
		instancer["name"].setValue( "instances" )

		GafferSceneTest.traverseScene( instancer["out"] )

	def testNamePlugDefaultValue( self ) :

		n = GafferScene.Instancer()
		self.assertEqual( n["name"].defaultValue(), "instances" )
		self.assertEqual( n["name"].getValue(), "instances" )

	def testAffects( self ) :

		n = GafferScene.Instancer()
		a = n.affects( n["name"] )
		self.assertGreaterEqual( { x.relativeName( n ) for x in a }, { "out.childNames", "out.bound", "out.set" } )

	def testParentBoundsWhenNoInstances( self ) :

		sphere = GafferScene.Sphere()
		sphere["type"].setValue( sphere.Type.Primitive ) # no points, so we can't instance onto it

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( sphere["out"] )
		instancer["parent"].setValue( "/sphere" )
		instancer["prototypes"].setInput( sphere["out"] )

		self.assertSceneValid( instancer["out"] )
		self.assertEqual( instancer["out"].bound( "/sphere" ), sphere["out"].bound( "/sphere" ) )

	def testEmptyName( self ) :

		plane = GafferScene.Plane()

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( plane["out"] )
		instancer["parent"].setValue( "/plane" )
		instancer["name"].setValue( "" )

		f = GafferScene.PathFilter()
		f["paths"].setValue( IECore.StringVectorData( [ "/plane" ] ) )

		deleteObject = GafferScene.DeleteObject()
		deleteObject["in"].setInput( plane["out"] )
		deleteObject["filter"].setInput( f["out"] )

		self.assertScenesEqual( instancer["out"], deleteObject["out"] )

	def testEmptyParent( self ) :

		plane = GafferScene.Plane()
		sphere = GafferScene.Sphere()

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( plane["out"] )
		instancer["prototypes"].setInput( sphere["out"] )

		instancer["parent"].setValue( "" )

		self.assertScenesEqual( instancer["out"], plane["out"] )
		self.assertSceneHashesEqual( instancer["out"], plane["out"] )

	def testSeedsAffectBound( self ) :

		plane = GafferScene.Plane()
		sphere = GafferScene.Sphere()

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( plane["out"] )
		instancer["prototypes"].setInput( sphere["out"] )

		instancer["parent"].setValue( "/plane" )

		h1 = instancer["out"].boundHash( "/plane/instances" )
		b1 = instancer["out"].bound( "/plane/instances" )

		plane["dimensions"].setValue( plane["dimensions"].getValue() * 2 )

		h2 = instancer["out"].boundHash( "/plane/instances" )
		b2 = instancer["out"].bound( "/plane/instances" )

		self.assertNotEqual( h1, h2 )
		self.assertNotEqual( b1, b2 )

	def testBoundHashIsStable( self ) :

		plane = GafferScene.Plane()
		sphere = GafferScene.Sphere()

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( plane["out"] )
		instancer["prototypes"].setInput( sphere["out"] )

		instancer["parent"].setValue( "/plane" )

		h = instancer["out"].boundHash( "/plane/instances" )
		for i in range( 0, 100 ) :
			self.assertEqual( instancer["out"].boundHash( "/plane/instances" ), h )

	def testObjectAffectsChildNames( self ) :

		plane = GafferScene.Plane()
		sphere = GafferScene.Sphere()

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( plane["out"] )
		instancer["prototypes"].setInput( sphere["out"] )
		instancer["parent"].setValue( "/plane" )

		cs = GafferTest.CapturingSlot( instancer.plugDirtiedSignal() )
		plane["divisions"]["x"].setValue( 2 )

		dirtiedPlugs = [ s[0] for s in cs ]

		self.assertTrue( instancer["out"]["childNames"] in dirtiedPlugs )
		self.assertTrue( instancer["out"]["bound"] in dirtiedPlugs )
		self.assertTrue( instancer["out"]["transform"] in dirtiedPlugs )

	def testPythonExpressionAndGIL( self ) :

		script = Gaffer.ScriptNode()

		script["plane"] = GafferScene.Plane()
		script["plane"]["divisions"].setValue( imath.V2i( 20 ) )

		script["sphere"] = GafferScene.Sphere()

		script["expression"] = Gaffer.Expression()
		script["expression"].setExpression( "parent['sphere']['radius'] = context.getFrame()" )

		script["instancer"] = GafferScene.Instancer()
		script["instancer"]["in"].setInput( script["plane"]["out"] )
		script["instancer"]["prototypes"].setInput( script["sphere"]["out"] )
		script["instancer"]["parent"].setValue( "/plane" )

		# The Instancer spawns its own threads, so if we don't release the GIL
		# when invoking it, and an upstream node enters Python, we'll end up
		# with a deadlock. Test that isn't the case. We increment the frame
		# between each test to ensure the expression result is not cached and
		# we do truly enter python.
		with Gaffer.Context() as c :

			c.setFrame( 1 )
			script["instancer"]["out"]["globals"].getValue()

			c.setFrame( 101 )
			script["instancer"]["out"]["globals"].hash()

			c["scene:path"] = IECore.InternedStringVectorData( [ "plane" ] )

			c.setFrame( 2 )
			script["instancer"]["out"]["bound"].getValue()
			c.setFrame( 3 )
			script["instancer"]["out"]["transform"].getValue()
			c.setFrame( 4 )
			script["instancer"]["out"]["object"].getValue()
			c.setFrame( 5 )
			script["instancer"]["out"]["attributes"].getValue()
			c.setFrame( 6 )
			script["instancer"]["out"]["childNames"].getValue()
			c.setFrame( 7 )

			c.setFrame( 102 )
			script["instancer"]["out"]["bound"].hash()
			c.setFrame( 103 )
			script["instancer"]["out"]["transform"].hash()
			c.setFrame( 104 )
			script["instancer"]["out"]["object"].hash()
			c.setFrame( 105 )
			script["instancer"]["out"]["attributes"].hash()
			c.setFrame( 106 )
			script["instancer"]["out"]["childNames"].hash()
			c.setFrame( 107 )

			# The same applies for the higher level helper functions on ScenePlug

			c.setFrame( 200 )
			script["instancer"]["out"].bound( "/plane" )
			c.setFrame( 201 )
			script["instancer"]["out"].transform( "/plane" )
			c.setFrame( 202 )
			script["instancer"]["out"].fullTransform( "/plane" )
			c.setFrame( 203 )
			script["instancer"]["out"].attributes( "/plane" )
			c.setFrame( 204 )
			script["instancer"]["out"].fullAttributes( "/plane" )
			c.setFrame( 205 )
			script["instancer"]["out"].object( "/plane" )
			c.setFrame( 206 )
			script["instancer"]["out"].childNames( "/plane" )
			c.setFrame( 207 )

			c.setFrame( 300 )
			script["instancer"]["out"].boundHash( "/plane" )
			c.setFrame( 301 )
			script["instancer"]["out"].transformHash( "/plane" )
			c.setFrame( 302 )
			script["instancer"]["out"].fullTransformHash( "/plane" )
			c.setFrame( 303 )
			script["instancer"]["out"].attributesHash( "/plane" )
			c.setFrame( 304 )
			script["instancer"]["out"].fullAttributesHash( "/plane" )
			c.setFrame( 305 )
			script["instancer"]["out"].objectHash( "/plane" )
			c.setFrame( 306 )
			script["instancer"]["out"].childNamesHash( "/plane" )
			c.setFrame( 307 )

	def testDynamicPlugsAndGIL( self ) :

		script = Gaffer.ScriptNode()

		script["plane"] = GafferScene.Plane()
		script["plane"]["divisions"].setValue( imath.V2i( 20 ) )

		script["sphere"] = GafferScene.Sphere()

		script["expression"] = Gaffer.Expression()
		script["expression"].setExpression( "parent['sphere']['radius'] = context.getFrame()" )

		script["instancer"] = GafferScene.Instancer()
		script["instancer"]["in"].setInput( script["plane"]["out"] )
		script["instancer"]["prototypes"].setInput( script["sphere"]["out"] )
		script["instancer"]["parent"].setValue( "/plane" )

		script["attributes"] = GafferScene.CustomAttributes()
		script["attributes"]["in"].setInput( script["instancer"]["out"] )

		script["outputs"] = GafferScene.Outputs()
		script["outputs"]["in"].setInput( script["attributes"]["out"] )

		# Simulate an InteractiveRender or Viewer traversal of the scene
		# every time it is dirtied. If the GIL isn't released when dirtiness
		# is signalled, we'll end up with a deadlock as the traversal enters
		# python on another thread to evaluate the expression. We increment the frame
		# between each test to ensure the expression result is not cached and
		# we do truly enter python.
		traverseConnection = Gaffer.Signals.ScopedConnection( GafferSceneTest.connectTraverseSceneToPlugDirtiedSignal( script["outputs"]["out"] ) )
		with Gaffer.Context() as c :

			c.setFrame( 1 )
			script["attributes"]["attributes"].addChild( Gaffer.NameValuePlug( "test1", IECore.IntData( 10 ) ) )

			c.setFrame( 2 )
			script["attributes"]["attributes"].addChild( Gaffer.NameValuePlug( "test2", IECore.IntData( 20 ), True ) )

			c.setFrame( 3 )
			script["attributes"]["attributes"].addMembers(
				IECore.CompoundData( {
					"test3" : 30,
					"test4" : 40,
				} )
			)

			c.setFrame( 4 )
			p = script["attributes"]["attributes"][0]
			del script["attributes"]["attributes"][p.getName()]

			c.setFrame( 5 )
			script["attributes"]["attributes"].addChild( p )

			c.setFrame( 6 )
			script["attributes"]["attributes"].removeChild( p )

			c.setFrame( 7 )
			script["attributes"]["attributes"].setChild( p.getName(), p )

			c.setFrame( 8 )
			script["attributes"]["attributes"].removeChild( p )

			c.setFrame( 9 )
			script["attributes"]["attributes"][p.getName()] = p

			c.setFrame( 10 )
			script["outputs"].addOutput( "test", IECoreScene.Output( "beauty.exr", "exr", "rgba" ) )

	def testLoadReferenceAndGIL( self ) :

		script = Gaffer.ScriptNode()

		script["plane"] = GafferScene.Plane()
		script["plane"]["divisions"].setValue( imath.V2i( 20 ) )

		script["sphere"] = GafferScene.Sphere()

		script["expression"] = Gaffer.Expression()
		script["expression"].setExpression( "parent['sphere']['radius'] = 0.1 + context.getFrame()" )

		script["instancer"] = GafferScene.Instancer()
		script["instancer"]["in"].setInput( script["plane"]["out"] )
		script["instancer"]["prototypes"].setInput( script["sphere"]["out"] )
		script["instancer"]["parent"].setValue( "/plane" )

		script["box"] = Gaffer.Box()
		script["box"]["in"] = GafferScene.ScenePlug( flags = Gaffer.Plug.Flags.Default | Gaffer.Plug.Flags.Dynamic )
		script["box"]["out"] = GafferScene.ScenePlug( direction = Gaffer.Plug.Direction.Out, flags = Gaffer.Plug.Flags.Default | Gaffer.Plug.Flags.Dynamic )
		script["box"]["out"].setInput( script["box"]["in"] )
		script["box"].exportForReference( self.temporaryDirectory() / "test.grf" )

		script["reference"] = Gaffer.Reference()
		script["reference"].load( self.temporaryDirectory() / "test.grf" )
		script["reference"]["in"].setInput( script["instancer"]["out"] )

		script["attributes"] = GafferScene.CustomAttributes()
		script["attributes"]["in"].setInput( script["reference"]["out"] )

		traverseConnection = Gaffer.Signals.ScopedConnection( GafferSceneTest.connectTraverseSceneToPlugDirtiedSignal( script["attributes"]["out"] ) )
		with Gaffer.Context() as c :

			script["reference"].load( self.temporaryDirectory() / "test.grf" )

	def testContextChangedAndGIL( self ) :

		script = Gaffer.ScriptNode()

		script["plane"] = GafferScene.Plane()
		script["plane"]["divisions"].setValue( imath.V2i( 20 ) )

		script["sphere"] = GafferScene.Sphere()

		script["expression"] = Gaffer.Expression()
		script["expression"].setExpression( "parent['sphere']['radius'] = context.get( 'minRadius', 0.1 ) + context.getFrame()" )

		script["instancer"] = GafferScene.Instancer()
		script["instancer"]["in"].setInput( script["plane"]["out"] )
		script["instancer"]["prototypes"].setInput( script["sphere"]["out"] )
		script["instancer"]["parent"].setValue( "/plane" )

		context = Gaffer.Context()
		traverseConnection = Gaffer.Signals.ScopedConnection( GafferSceneTest.connectTraverseSceneToContextChangedSignal( script["instancer"]["out"], context ) )
		with context :

			context.setFrame( 10 )
			context.setFramesPerSecond( 50 )
			context.setTime( 1 )

			context.set( "a", 1 )
			context.set( "a", 2.0 )
			context.set( "a", "a" )
			context.set( "a", imath.V2i() )
			context.set( "a", imath.V3i() )
			context.set( "a", imath.V2f() )
			context.set( "a", imath.V3f() )
			context.set( "a", imath.Color3f() )
			context.set( "a", IECore.BoolData( True ) )

			context["b"] = 1
			context["b"] = 2.0
			context["b"] = "b"
			context["b"] = imath.V2i()
			context["b"] = imath.V3i()
			context["b"] = imath.V2f()
			context["b"] = imath.V3f()
			context["b"] = imath.Color3f()
			context["b"] = IECore.BoolData( True )

			with Gaffer.Signals.BlockedConnection( traverseConnection ) :
				# Must add it with the connection disabled, otherwise
				# the addition causes a traversal, and then remove() gets
				# all its results from the cache.
				context["minRadius"] = 0.2

			context.remove( "minRadius" )

			with Gaffer.Signals.BlockedConnection( traverseConnection ) :
				context["minRadius"] = 0.3

			del context["minRadius"]

	def testDispatchAndGIL( self ) :

		script = Gaffer.ScriptNode()

		script["plane"] = GafferScene.Plane()
		script["plane"]["divisions"].setValue( imath.V2i( 20 ) )

		script["sphere"] = GafferScene.Sphere()

		script["expression"] = Gaffer.Expression()
		script["expression"].setExpression( "parent['sphere']['radius'] = context.get( 'minRadius', 0.1 ) + context.getFrame()" )

		script["instancer"] = GafferScene.Instancer()
		script["instancer"]["in"].setInput( script["plane"]["out"] )
		script["instancer"]["prototypes"].setInput( script["sphere"]["out"] )
		script["instancer"]["parent"].setValue( "/plane" )

		script["pythonCommand"] = GafferDispatch.PythonCommand()
		script["pythonCommand"]["command"].setValue( "pass" )

		traverseConnection = Gaffer.Signals.ScopedConnection( GafferSceneTest.connectTraverseSceneToPreDispatchSignal( script["instancer"]["out"] ) )

		dispatcher = GafferDispatch.LocalDispatcher()
		dispatcher["jobsDirectory"].setValue( self.temporaryDirectory() )

		with Gaffer.Context() as c :
			for i in range( 1, 10 ) :
				c.setFrame( i )
				dispatcher.dispatch( [ script["pythonCommand"] ] )

	def testTransform( self ) :

		point = IECoreScene.PointsPrimitive( IECore.V3fVectorData( [ imath.V3f( 4, 0, 0 ) ] ) )
		point["orientation"] = IECoreScene.PrimitiveVariable(
			IECoreScene.PrimitiveVariable.Interpolation.Vertex,
			IECore.QuatfVectorData( [ imath.Quatf().setAxisAngle( imath.V3f( 0, 1, 0 ), math.pi / 2.0 ) ] )
		)
		point["scale"] = IECoreScene.PrimitiveVariable(
			IECoreScene.PrimitiveVariable.Interpolation.Vertex,
			IECore.V3fVectorData( [ imath.V3f( 2, 3, 4 ) ] )
		)
		point["uniformScale"] = IECoreScene.PrimitiveVariable(
			IECoreScene.PrimitiveVariable.Interpolation.Vertex,
			IECore.FloatVectorData( [ 10 ] )
		)

		objectToScene = GafferScene.ObjectToScene()
		objectToScene["object"].setValue( point )

		sphere = GafferScene.Sphere()

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( objectToScene["out"] )
		instancer["prototypes"].setInput( sphere["out"] )
		instancer["parent"].setValue( "/object" )

		self.assertEqual( instancer["out"].transform( "/object/instances/sphere/0" ), imath.M44f().translate( imath.V3f( 4, 0, 0 ) ) )

		instancer["orientation"].setValue( "orientation" )
		self.assertTrue(
			imath.V3f( 4, 0, -1 ).equalWithAbsError(
				imath.V3f( 1, 0, 0 ) * instancer["out"].transform( "/object/instances/sphere/0" ),
				0.00001
			)
		)

		instancer["scale"].setValue( "scale" )
		self.assertTrue(
			imath.V3f( 4, 0, -2 ).equalWithAbsError(
				imath.V3f( 1, 0, 0 ) * instancer["out"].transform( "/object/instances/sphere/0" ),
				0.00001
			)
		)

		instancer["scale"].setValue( "uniformScale" )
		self.assertTrue(
			imath.V3f( 4, 0, -10 ).equalWithAbsError(
				imath.V3f( 1, 0, 0 ) * instancer["out"].transform( "/object/instances/sphere/0" ),
				0.00001
			)
		)

	def testIndexedRootsListWithEmptyList( self ) :

		points = IECoreScene.PointsPrimitive( IECore.V3fVectorData( [ imath.V3f( x, 0, 0 ) for x in range( 0, 4 ) ] ) )
		points["index"] = IECoreScene.PrimitiveVariable(
			IECoreScene.PrimitiveVariable.Interpolation.Vertex,
			IECore.IntVectorData( [ 0, 1, 1, 0 ] ),
		)

		objectToScene = GafferScene.ObjectToScene()
		objectToScene["object"].setValue( points )

		sphere = GafferScene.Sphere()
		cube = GafferScene.Cube()
		instances = GafferScene.Parent()
		instances["in"].setInput( sphere["out"] )
		instances["children"][0].setInput( cube["out"] )
		instances["parent"].setValue( "/" )

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( objectToScene["out"] )
		instancer["prototypes"].setInput( instances["out"] )
		instancer["parent"].setValue( "/object" )
		instancer["prototypeIndex"].setValue( "index" )

		self.assertEqual( instancer["out"].childNames( "/object/instances" ), IECore.InternedStringVectorData( [ "sphere", "cube" ] ) )
		self.assertEqual( instancer["out"].childNames( "/object/instances/sphere" ), IECore.InternedStringVectorData( [ "0", "3" ] ) )
		self.assertEqual( instancer["out"].childNames( "/object/instances/cube" ), IECore.InternedStringVectorData( [ "1", "2" ] ) )
		self.assertEqual( instancer["out"].childNames( "/object/instances/sphere/0" ), IECore.InternedStringVectorData() )
		self.assertEqual( instancer["out"].childNames( "/object/instances/sphere/3" ), IECore.InternedStringVectorData() )
		self.assertEqual( instancer["out"].childNames( "/object/instances/cube/1" ), IECore.InternedStringVectorData() )
		self.assertEqual( instancer["out"].childNames( "/object/instances/cube/2" ), IECore.InternedStringVectorData() )

		self.assertEqual( instancer["out"].object( "/object/instances" ), IECore.NullObject.defaultNullObject() )
		self.assertEqual( instancer["out"].object( "/object/instances/sphere" ), IECore.NullObject.defaultNullObject() )
		self.assertEqual( instancer["out"].object( "/object/instances/cube" ), IECore.NullObject.defaultNullObject() )
		self.assertEqual( instancer["out"].object( "/object/instances/sphere/0" ), sphere["out"].object( "/sphere" ) )
		self.assertEqual( instancer["out"].object( "/object/instances/sphere/3" ), sphere["out"].object( "/sphere" ) )
		self.assertEqual( instancer["out"].object( "/object/instances/cube/1" ), cube["out"].object( "/cube" ) )
		self.assertEqual( instancer["out"].object( "/object/instances/cube/2" ), cube["out"].object( "/cube" ) )

		self.assertSceneValid( instancer["out"] )

	def buildPrototypeRootsScript( self ) :

		# we don't strictly require a script, but its the easiest way to
		# maintain references to all the nodes for use in client tests.
		script = Gaffer.ScriptNode()

		points = IECoreScene.PointsPrimitive( IECore.V3fVectorData( [ imath.V3f( x, 0, 0 ) for x in range( 0, 4 ) ] ) )
		points["index"] = IECoreScene.PrimitiveVariable(
			IECoreScene.PrimitiveVariable.Interpolation.Vertex,
			IECore.IntVectorData( [ 0, 1, 1, 0 ] ),
		)
		# for use with RootPerVertex mode
		points["root"] = IECoreScene.PrimitiveVariable(
			IECoreScene.PrimitiveVariable.Interpolation.Vertex,
			IECore.StringVectorData( [ "/foo", "/bar" ] ),
			IECore.IntVectorData( [ 0, 1, 1, 0 ] ),
		)

		script["objectToScene"] = GafferScene.ObjectToScene()
		script["objectToScene"]["object"].setValue( points )
		# for use with IndexedRootsVariable mode
		script["variables"] = GafferScene.PrimitiveVariables()
		script["variables"]["primitiveVariables"].addChild(
			Gaffer.NameValuePlug(
				"prototypeRoots",
				Gaffer.StringVectorDataPlug( "value", defaultValue = IECore.StringVectorData( [  ] ), flags = Gaffer.Plug.Flags.Default | Gaffer.Plug.Flags.Dynamic, ),
				True,
				"prototypeRoots",
				Gaffer.Plug.Flags.Default | Gaffer.Plug.Flags.Dynamic
			)
		)
		script["variables"]["primitiveVariables"]["prototypeRoots"]["name"].setValue( 'prototypeRoots' )
		script["variables"]["in"].setInput( script["objectToScene"]["out"] )
		script["filter"] = GafferScene.PathFilter()
		script["filter"]["paths"].setValue( IECore.StringVectorData( [ "/object" ] ) )
		script["variables"]["filter"].setInput( script["filter"]["out"] )

		# /foo/bar/sphere
		script["sphere"] = GafferScene.Sphere()
		script["group"] = GafferScene.Group()
		script["group"]["name"].setValue( "bar" )
		script["group"]["in"][0].setInput( script["sphere"]["out"] )
		script["group2"] = GafferScene.Group()
		script["group2"]["name"].setValue( "foo" )
		script["group2"]["in"][0].setInput( script["group"]["out"] )

		# /bar/baz/cube
		script["cube"] = GafferScene.Cube()
		script["group3"] = GafferScene.Group()
		script["group3"]["name"].setValue( "baz" )
		script["group3"]["in"][0].setInput( script["cube"]["out"] )
		script["group4"] = GafferScene.Group()
		script["group4"]["name"].setValue( "bar" )
		script["group4"]["in"][0].setInput( script["group3"]["out"] )

		script["prototypes"] = GafferScene.Parent()
		script["prototypes"]["in"].setInput( script["group2"]["out"] )
		script["prototypes"]["children"][0].setInput( script["group4"]["out"] )
		script["prototypes"]["parent"].setValue( "/" )

		script["instancer"] = GafferScene.Instancer()
		script["instancer"]["in"].setInput( script["variables"]["out"] )
		script["instancer"]["prototypes"].setInput( script["prototypes"]["out"] )
		script["instancer"]["parent"].setValue( "/object" )
		script["instancer"]["prototypeIndex"].setValue( "index" )

		return script

	def assertRootsMatchPrototypeSceneChildren( self, script ) :

		self.assertEqual( script["instancer"]["out"].childNames( "/object/instances" ), IECore.InternedStringVectorData( [ "foo", "bar" ] ) )
		self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/foo" ), IECore.InternedStringVectorData( [ "0", "3" ] ) )
		self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/bar" ), IECore.InternedStringVectorData( [ "1", "2" ] ) )

		self.assertEqual( script["instancer"]["out"].object( "/object/instances" ), IECore.NullObject.defaultNullObject() )
		self.assertEqual( script["instancer"]["out"].object( "/object/instances/foo" ), IECore.NullObject.defaultNullObject() )
		self.assertEqual( script["instancer"]["out"].object( "/object/instances/bar" ), IECore.NullObject.defaultNullObject() )

		for i in [ "0", "3" ] :

			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/foo/{i}".format( i=i ) ), IECore.InternedStringVectorData( [ "bar" ] ) )
			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/foo/{i}/bar".format( i=i ) ), IECore.InternedStringVectorData( [ "sphere" ] ) )

			self.assertEqual( script["instancer"]["out"].object( "/object/instances/foo/{i}".format( i=i ) ), IECore.NullObject.defaultNullObject() )
			self.assertEqual( script["instancer"]["out"].object( "/object/instances/foo/{i}/bar".format( i=i ) ), IECore.NullObject.defaultNullObject() )
			self.assertEqual( script["instancer"]["out"].object( "/object/instances/foo/{i}/bar/sphere".format( i=i ) ), script["sphere"]["out"].object( "/sphere" ) )

		for i in [ "1", "2" ] :

			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/bar/{i}".format( i=i ) ), IECore.InternedStringVectorData( [ "baz" ] ) )
			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/bar/{i}/baz".format( i=i ) ), IECore.InternedStringVectorData( [ "cube" ] ) )

			self.assertEqual( script["instancer"]["out"].object( "/object/instances/bar/{i}".format( i=i ) ), IECore.NullObject.defaultNullObject() )
			self.assertEqual( script["instancer"]["out"].object( "/object/instances/bar/{i}/baz".format( i=i ) ), IECore.NullObject.defaultNullObject() )
			self.assertEqual( script["instancer"]["out"].object( "/object/instances/bar/{i}/baz/cube".format( i=i ) ), script["cube"]["out"].object( "/cube" ) )

		self.assertSceneValid( script["instancer"]["out"] )

	def assertUnderspecifiedRoots( self, script ) :

		self.assertEqual( script["instancer"]["out"].childNames( "/object/instances" ), IECore.InternedStringVectorData( [] ) )
		self.assertEqual( script["instancer"]["out"].object( "/object/instances" ), IECore.NullObject.defaultNullObject() )

	def assertSingleRoot( self, script ) :

		self.assertEqual( script["instancer"]["out"].childNames( "/object/instances" ), IECore.InternedStringVectorData( [ "foo" ] ) )
		self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/foo" ), IECore.InternedStringVectorData( [ "0", "1", "2", "3" ] ) )

		for i in [ "0", "1", "2", "3" ] :

			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/foo/{i}".format( i=i ) ), IECore.InternedStringVectorData( [ "bar" ] ) )
			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/foo/{i}/bar".format( i=i ) ), IECore.InternedStringVectorData( [ "sphere" ] ) )

			self.assertEqual( script["instancer"]["out"].object( "/object/instances/foo/{i}".format( i=i ) ), IECore.NullObject.defaultNullObject() )
			self.assertEqual( script["instancer"]["out"].object( "/object/instances/foo/{i}/bar".format( i=i ) ), IECore.NullObject.defaultNullObject() )
			self.assertEqual( script["instancer"]["out"].object( "/object/instances/foo/{i}/bar/sphere".format( i=i ) ), script["sphere"]["out"].object( "/sphere" ) )

		self.assertSceneValid( script["instancer"]["out"] )

	def assertConflictingRootNames( self, script ) :

		self.assertEqual( script["instancer"]["out"].childNames( "/object/instances" ), IECore.InternedStringVectorData( [ "bar", "bar1" ] ) )
		self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/bar" ), IECore.InternedStringVectorData( [ "0", "3" ] ) )
		self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/bar1" ), IECore.InternedStringVectorData( [ "1", "2" ] ) )

		self.assertEqual( script["instancer"]["out"].object( "/object/instances" ), IECore.NullObject.defaultNullObject() )
		self.assertEqual( script["instancer"]["out"].object( "/object/instances/bar" ), IECore.NullObject.defaultNullObject() )
		self.assertEqual( script["instancer"]["out"].object( "/object/instances/bar1" ), IECore.NullObject.defaultNullObject() )

		for i in [ "0", "3" ] :

			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/bar/{i}".format( i=i ) ), IECore.InternedStringVectorData( [ "sphere" ] ) )
			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/bar/{i}/sphere".format( i=i ) ), IECore.InternedStringVectorData( [] ) )

			self.assertEqual( script["instancer"]["out"].object( "/object/instances/bar/{i}".format( i=i ) ), IECore.NullObject.defaultNullObject() )
			self.assertEqual( script["instancer"]["out"].object( "/object/instances/bar/{i}/sphere".format( i=i ) ), script["sphere"]["out"].object( "/sphere" ) )

		for i in [ "1", "2" ] :

			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/bar1/{i}".format( i=i ) ), IECore.InternedStringVectorData( [ "baz" ] ) )
			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/bar1/{i}/baz".format( i=i ) ), IECore.InternedStringVectorData( [ "cube" ] ) )

			self.assertEqual( script["instancer"]["out"].object( "/object/instances/bar1/{i}".format( i=i ) ), IECore.NullObject.defaultNullObject() )
			self.assertEqual( script["instancer"]["out"].object( "/object/instances/bar1/{i}/baz".format( i=i ) ), IECore.NullObject.defaultNullObject() )
			self.assertEqual( script["instancer"]["out"].object( "/object/instances/bar1/{i}/baz/cube".format( i=i ) ), script["cube"]["out"].object( "/cube" ) )

		self.assertSceneValid( script["instancer"]["out"] )

	def assertSwappedRoots( self, script ) :

		self.assertEqual( script["instancer"]["out"].childNames( "/object/instances" ), IECore.InternedStringVectorData( [ "bar", "foo" ] ) )
		self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/bar" ), IECore.InternedStringVectorData( [ "0", "3" ] ) )
		self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/foo" ), IECore.InternedStringVectorData( [ "1", "2" ] ) )

		self.assertEqual( script["instancer"]["out"].object( "/object/instances" ), IECore.NullObject.defaultNullObject() )
		self.assertEqual( script["instancer"]["out"].object( "/object/instances/bar" ), IECore.NullObject.defaultNullObject() )
		self.assertEqual( script["instancer"]["out"].object( "/object/instances/foo" ), IECore.NullObject.defaultNullObject() )

		for i in [ "0", "3" ] :

			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/bar/{i}".format( i=i ) ), IECore.InternedStringVectorData( [ "baz" ] ) )
			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/bar/{i}/baz".format( i=i ) ), IECore.InternedStringVectorData( [ "cube" ] ) )

			self.assertEqual( script["instancer"]["out"].object( "/object/instances/bar/{i}".format( i=i ) ), IECore.NullObject.defaultNullObject() )
			self.assertEqual( script["instancer"]["out"].object( "/object/instances/bar/{i}/baz".format( i=i ) ), IECore.NullObject.defaultNullObject() )
			self.assertEqual( script["instancer"]["out"].object( "/object/instances/bar/{i}/baz/cube".format( i=i ) ), script["cube"]["out"].object( "/cube" ) )

		for i in [ "1", "2" ] :

			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/foo/{i}".format( i=i ) ), IECore.InternedStringVectorData( [ "bar" ] ) )
			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/foo/{i}/bar".format( i=i ) ), IECore.InternedStringVectorData( [ "sphere" ] ) )

			self.assertEqual( script["instancer"]["out"].object( "/object/instances/foo/{i}".format( i=i ) ), IECore.NullObject.defaultNullObject() )
			self.assertEqual( script["instancer"]["out"].object( "/object/instances/foo/{i}/bar".format( i=i ) ), IECore.NullObject.defaultNullObject() )
			self.assertEqual( script["instancer"]["out"].object( "/object/instances/foo/{i}/bar/sphere".format( i=i ) ), script["sphere"]["out"].object( "/sphere" ) )

		self.assertSceneValid( script["instancer"]["out"] )

	def assertSkippedRoots( self, script ) :

		self.assertEqual( script["instancer"]["out"].childNames( "/object/instances" ), IECore.InternedStringVectorData( [ "bar" ] ) )
		self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/bar" ), IECore.InternedStringVectorData( [ "1", "2" ] ) )

		self.assertEqual( script["instancer"]["out"].object( "/object/instances" ), IECore.NullObject.defaultNullObject() )
		self.assertEqual( script["instancer"]["out"].object( "/object/instances/bar" ), IECore.NullObject.defaultNullObject() )

		for i in [ "1", "2" ] :

			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/bar/{i}".format( i=i ) ), IECore.InternedStringVectorData( [ "baz" ] ) )
			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/bar/{i}/baz".format( i=i ) ), IECore.InternedStringVectorData( [ "cube" ] ) )

			self.assertEqual( script["instancer"]["out"].object( "/object/instances/bar/{i}".format( i=i ) ), IECore.NullObject.defaultNullObject() )
			self.assertEqual( script["instancer"]["out"].object( "/object/instances/bar/{i}/baz".format( i=i ) ), IECore.NullObject.defaultNullObject() )
			self.assertEqual( script["instancer"]["out"].object( "/object/instances/bar/{i}/baz/cube".format( i=i ) ), script["cube"]["out"].object( "/cube" ) )

		self.assertSceneValid( script["instancer"]["out"] )

	def assertRootsToLeaves( self, script ) :

		self.assertEqual( script["instancer"]["out"].childNames( "/object/instances" ), IECore.InternedStringVectorData( [ "sphere", "cube" ] ) )
		self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/sphere" ), IECore.InternedStringVectorData( [ "0", "3" ] ) )
		self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/cube" ), IECore.InternedStringVectorData( [ "1", "2" ] ) )

		self.assertEqual( script["instancer"]["out"].object( "/object/instances" ), IECore.NullObject.defaultNullObject() )
		self.assertEqual( script["instancer"]["out"].object( "/object/instances/sphere" ), IECore.NullObject.defaultNullObject() )
		self.assertEqual( script["instancer"]["out"].object( "/object/instances/cube" ), IECore.NullObject.defaultNullObject() )

		for i in [ "0", "3" ] :

			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/sphere/{i}".format( i=i ) ), IECore.InternedStringVectorData( [] ) )

			self.assertEqual( script["instancer"]["out"].object( "/object/instances/sphere/{i}".format( i=i ) ), script["sphere"]["out"].object( "/sphere" ) )

		for i in [ "1", "2" ] :

			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/cube/{i}".format( i=i ) ), IECore.InternedStringVectorData( [] ) )

			self.assertEqual( script["instancer"]["out"].object( "/object/instances/cube/{i}".format( i=i ) ), script["cube"]["out"].object( "/cube" ) )

		self.assertSceneValid( script["instancer"]["out"] )

	def assertRootsToRoot( self, script ) :

		self.assertEqual( script["instancer"]["out"].childNames( "/object/instances" ), IECore.InternedStringVectorData( [ "root" ] ) )
		self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/root" ), IECore.InternedStringVectorData( [ "0", "1", "2", "3" ] ) )

		self.assertEqual( script["instancer"]["out"].object( "/object/instances" ), IECore.NullObject.defaultNullObject() )
		self.assertEqual( script["instancer"]["out"].object( "/object/instances/root" ), IECore.NullObject.defaultNullObject() )

		for i in [ "0", "1", "2", "3" ] :

			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/root/{i}".format( i=i ) ), IECore.InternedStringVectorData( [ "foo", "bar" ] ) )
			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/root/{i}/foo".format( i=i ) ), IECore.InternedStringVectorData( [ "bar" ] ) )
			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/root/{i}/foo/bar".format( i=i ) ), IECore.InternedStringVectorData( [ "sphere" ] ) )
			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/root/{i}/bar".format( i=i ) ), IECore.InternedStringVectorData( [ "baz" ] ) )
			self.assertEqual( script["instancer"]["out"].childNames( "/object/instances/root/{i}/bar/baz".format( i=i ) ), IECore.InternedStringVectorData( [ "cube" ] ) )

			self.assertEqual( script["instancer"]["out"].object( "/object/instances/root/{i}".format( i=i ) ), IECore.NullObject.defaultNullObject() )
			self.assertEqual( script["instancer"]["out"].object( "/object/instances/root/{i}/foo".format( i=i ) ), IECore.NullObject.defaultNullObject() )
			self.assertEqual( script["instancer"]["out"].object( "/object/instances/root/{i}/foo/bar".format( i=i ) ), IECore.NullObject.defaultNullObject() )
			self.assertEqual( script["instancer"]["out"].object( "/object/instances/root/{i}/foo/bar/sphere".format( i=i ) ), script["sphere"]["out"].object( "/sphere" ) )
			self.assertEqual( script["instancer"]["out"].object( "/object/instances/root/{i}/bar".format( i=i ) ), IECore.NullObject.defaultNullObject() )
			self.assertEqual( script["instancer"]["out"].object( "/object/instances/root/{i}/bar/baz".format( i=i ) ), IECore.NullObject.defaultNullObject() )
			self.assertEqual( script["instancer"]["out"].object( "/object/instances/root/{i}/bar/baz/cube".format( i=i ) ), script["cube"]["out"].object( "/cube" ) )

	def testIndexedRootsList( self ) :

		script = self.buildPrototypeRootsScript()
		script["instancer"]["prototypeMode"].setValue( GafferScene.Instancer.PrototypeMode.IndexedRootsList )

		script["instancer"]["prototypeRootsList"].setValue( IECore.StringVectorData( [] ) )
		self.assertRootsMatchPrototypeSceneChildren( script )

		script["instancer"]["prototypeRootsList"].setValue( IECore.StringVectorData( [ "", ] ) )
		self.assertUnderspecifiedRoots( script )

		script["instancer"]["prototypeRootsList"].setValue( IECore.StringVectorData( [ "/foo", ] ) )
		self.assertSingleRoot( script )

		# roots list matching the prototype root children
		# we expect the same results as without a roots list
		script["instancer"]["prototypeRootsList"].setValue( IECore.StringVectorData( [ "/foo", "/bar" ] ) )
		self.assertRootsMatchPrototypeSceneChildren( script )

		script["instancer"]["prototypeRootsList"].setValue( IECore.StringVectorData( [ "/foo/bar", "/bar" ] ) )
		self.assertConflictingRootNames( script )

		# opposite order to the prototype root children
		script["instancer"]["prototypeRootsList"].setValue( IECore.StringVectorData( [ "/bar", "/foo" ] ) )
		self.assertSwappedRoots( script )

		script["instancer"]["prototypeRootsList"].setValue( IECore.StringVectorData( [ "", "/bar" ] ) )
		self.assertSkippedRoots( script )

		# roots all the way to the leaf level of the prototype scene
		script["instancer"]["prototypeRootsList"].setValue( IECore.StringVectorData( [ "/foo/bar/sphere", "/bar/baz/cube" ] ) )
		self.assertRootsToLeaves( script )

		# we can specify the root of the prototype scene
		script["instancer"]["prototypeRootsList"].setValue( IECore.StringVectorData( [ "/" ] ) )
		self.assertRootsToRoot( script )

		script["instancer"]["prototypeRootsList"].setValue( IECore.StringVectorData( [ "/foo", "/does/not/exist" ] ) )
		self.assertRaisesRegex(
			Gaffer.ProcessException, '.*Prototype root "/does/not/exist" does not exist.*',
			script["instancer"]["out"].childNames, "/object/instances",
		)

	def testIndexedRootsVariable( self ) :

		script = self.buildPrototypeRootsScript()
		script["instancer"]["prototypeMode"].setValue( GafferScene.Instancer.PrototypeMode.IndexedRootsVariable )

		script["variables"]["primitiveVariables"]["prototypeRoots"]["value"].setValue( IECore.StringVectorData( [] ) )
		self.assertRaisesRegex(
			Gaffer.ProcessException, ".*must specify at least one root location.*",
			script["instancer"]["out"].childNames, "/object/instances",
		)

		script["variables"]["primitiveVariables"]["prototypeRoots"]["value"].setValue( IECore.StringVectorData( [ "", ] ) )
		self.assertUnderspecifiedRoots( script )

		script["variables"]["primitiveVariables"]["prototypeRoots"]["value"].setValue( IECore.StringVectorData( [ "/foo", ] ) )
		self.assertSingleRoot( script )

		# roots list matching the prototype root children
		# we expect the same results as without a roots list
		script["variables"]["primitiveVariables"]["prototypeRoots"]["value"].setValue( IECore.StringVectorData( [ "/foo", "/bar" ] ) )
		self.assertRootsMatchPrototypeSceneChildren( script )

		script["variables"]["primitiveVariables"]["prototypeRoots"]["value"].setValue( IECore.StringVectorData( [ "/foo/bar", "/bar" ] ) )
		self.assertConflictingRootNames( script )

		# opposite order to the prototype root children
		script["variables"]["primitiveVariables"]["prototypeRoots"]["value"].setValue( IECore.StringVectorData( [ "/bar", "/foo" ] ) )
		self.assertSwappedRoots( script )

		script["variables"]["primitiveVariables"]["prototypeRoots"]["value"].setValue( IECore.StringVectorData( [ "", "/bar" ] ) )
		self.assertSkippedRoots( script )

		# roots all the way to the leaf level of the prototype scene
		script["variables"]["primitiveVariables"]["prototypeRoots"]["value"].setValue( IECore.StringVectorData( [ "/foo/bar/sphere", "/bar/baz/cube" ] ) )
		self.assertRootsToLeaves( script )

		# we can specify the root of the prototype scene
		script["variables"]["primitiveVariables"]["prototypeRoots"]["value"].setValue( IECore.StringVectorData( [ "/" ] ) )
		self.assertRootsToRoot( script )

		script["variables"]["primitiveVariables"]["prototypeRoots"]["value"].setValue( IECore.StringVectorData( [ "/foo", "/does/not/exist" ] ) )
		self.assertRaisesRegex(
			Gaffer.ProcessException, '.*Prototype root "/does/not/exist" does not exist.*',
			script["instancer"]["out"].childNames, "/object/instances",
		)

		script["instancer"]["prototypeRoots"].setValue( "notAPrimVar" )
		self.assertRaisesRegex(
			Gaffer.ProcessException, ".*must be Constant StringVectorData when using IndexedRootsVariable mode.*does not exist.*",
			script["instancer"]["out"].childNames, "/object/instances",
		)

		# the vertex primvar should fail
		script["instancer"]["prototypeRoots"].setValue( "root" )
		self.assertRaisesRegex(
			Gaffer.ProcessException, ".*must be Constant StringVectorData when using IndexedRootsVariable mode.*",
			script["instancer"]["out"].childNames, "/object/instances",
		)

	def testRootPerVertex( self ) :

		script = self.buildPrototypeRootsScript()
		script["instancer"]["prototypeMode"].setValue( GafferScene.Instancer.PrototypeMode.RootPerVertex )
		script["instancer"]["prototypeRoots"].setValue( "root" )

		def updateRoots( roots, indices ) :

			points = script["objectToScene"]["object"].getValue()
			points["root"] = IECoreScene.PrimitiveVariable( points["root"].interpolation, roots, indices )
			self.assertTrue( points.arePrimitiveVariablesValid() )
			script["objectToScene"]["object"].setValue( points )

		updateRoots( IECore.StringVectorData( [ "", ] ), IECore.IntVectorData( [ 0, 0, 0, 0 ] ) )
		self.assertUnderspecifiedRoots( script )

		updateRoots( IECore.StringVectorData( [ "/foo", ] ), IECore.IntVectorData( [ 0, 0, 0, 0 ] ) )
		self.assertSingleRoot( script )

		# roots list matching the prototype root children
		# we expect the same results as without a roots list
		updateRoots( IECore.StringVectorData( [ "/foo", "/bar" ] ), IECore.IntVectorData( [ 0, 1, 1, 0 ] ) )
		self.assertRootsMatchPrototypeSceneChildren( script )

		updateRoots( IECore.StringVectorData( [ "/foo/bar", "/bar" ] ), IECore.IntVectorData( [ 0, 1, 1, 0 ] ) )
		self.assertConflictingRootNames( script )

		# opposite order to the prototype root children
		updateRoots( IECore.StringVectorData( [ "/bar", "/foo" ] ), IECore.IntVectorData( [ 0, 1, 1, 0 ] ) )
		self.assertSwappedRoots( script )

		updateRoots( IECore.StringVectorData( [ "", "/bar" ] ), IECore.IntVectorData( [ 0, 1, 1, 0 ] ) )
		self.assertSkippedRoots( script )

		# roots all the way to the leaf level of the prototype scene
		updateRoots( IECore.StringVectorData( [ "/foo/bar/sphere", "/bar/baz/cube" ] ), IECore.IntVectorData( [ 0, 1, 1, 0 ] ) )
		self.assertRootsToLeaves( script )

		# we can specify the root of the prototype scene
		updateRoots( IECore.StringVectorData( [ "/", ] ), IECore.IntVectorData( [ 0, 0, 0, 0 ] ) )
		self.assertRootsToRoot( script )

		updateRoots( IECore.StringVectorData( [ "/foo", "/does/not/exist" ] ), IECore.IntVectorData( [ 0, 1, 1, 0 ] ) )
		self.assertRaisesRegex(
			Gaffer.ProcessException, '.*Prototype root "/does/not/exist" does not exist.*',
			script["instancer"]["out"].childNames, "/object/instances",
		)

		script["instancer"]["prototypeRoots"].setValue( "notAPrimVar" )
		self.assertRaisesRegex(
			Gaffer.ProcessException, ".*must be Vertex StringVectorData when using RootPerVertex mode.*does not exist.*",
			script["instancer"]["out"].childNames, "/object/instances",
		)

		# the constant primvar should fail
		script["instancer"]["prototypeRoots"].setValue( "prototypeRoots" )
		self.assertRaisesRegex(
			Gaffer.ProcessException, ".*must be Vertex StringVectorData when using RootPerVertex mode.*",
			script["instancer"]["out"].childNames, "/object/instances",
		)

	def testSets( self ) :

		points = IECoreScene.PointsPrimitive( IECore.V3fVectorData( [ imath.V3f( x, 0, 0 ) for x in range( 0, 4 ) ] ) )
		points["index"] = IECoreScene.PrimitiveVariable(
			IECoreScene.PrimitiveVariable.Interpolation.Vertex,
			IECore.IntVectorData( [ 0, 1, 1, 0 ] ),
		)

		objectToScene = GafferScene.ObjectToScene()
		objectToScene["object"].setValue( points )

		sphere = GafferScene.Sphere()
		sphere["sets"].setValue( "sphereSet" )

		cube = GafferScene.Cube()
		cube["sets"].setValue( "cubeSet" )
		cubeGroup = GafferScene.Group()
		cubeGroup["name"].setValue( "cubeGroup" )
		cubeGroup["in"][0].setInput( cube["out"] )

		instances = GafferScene.Parent()
		instances["in"].setInput( sphere["out"] )
		instances["children"][0].setInput( cubeGroup["out"] )
		instances["parent"].setValue( "/" )

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( objectToScene["out"] )
		instancer["prototypes"].setInput( instances["out"] )
		instancer["parent"].setValue( "/object" )
		instancer["prototypeIndex"].setValue( "index" )

		self.assertEqual(
			instancer["out"]["setNames"].getValue(),
			IECore.InternedStringVectorData( [ "sphereSet", "cubeSet" ] )
		)

		self.assertEqual(
			set( instancer["out"].set( "sphereSet" ).value.paths() ),
			{
				"/object/instances/sphere/0",
				"/object/instances/sphere/3",
			}
		)

		self.assertEqual(
			set( instancer["out"].set( "cubeSet" ).value.paths() ),
			{
				"/object/instances/cubeGroup/1/cube",
				"/object/instances/cubeGroup/2/cube",
			}
		)

		# Test encapsulation options
		encapInstancer = GafferScene.Instancer()
		encapInstancer["in"].setInput( objectToScene["out"] )
		encapInstancer["prototypes"].setInput( instances["out"] )
		encapInstancer["parent"].setValue( "/object" )
		encapInstancer["prototypeIndex"].setValue( "index" )
		encapInstancer["encapsulateInstanceGroups"].setValue( True )

		unencapFilter = GafferScene.PathFilter()
		unencapFilter["paths"].setValue( IECore.StringVectorData( [ "/..." ] ) )

		unencap = GafferScene.Unencapsulate()
		unencap["in"].setInput( encapInstancer["out"] )
		unencap["filter"].setInput( unencapFilter["out"] )

		# Sets should be empty while encapsulated
		self.assertEqual( encapInstancer["out"].set( "sphereSet" ).value.paths(), [] )
		self.assertEqual( encapInstancer["out"].set( "cubeSet" ).value.paths(), [] )
		# But should match after unencapsulating
		self.assertScenesEqual( unencap["out"], instancer["out"] )

	def testSetsWithDeepPrototypeRoots( self ) :

		script = self.buildPrototypeRootsScript()

		script["sphere"]["sets"].setValue( "sphereSet" )
		script["cube"]["sets"].setValue( "cubeSet" )

		script["set"] = GafferScene.Set()
		script["set"]["name"].setValue( "barSet" )
		script["set"]["in"].setInput( script["prototypes"]["out"] )
		script["barFilter"] = GafferScene.PathFilter()
		script["barFilter"]["paths"].setValue( IECore.StringVectorData( [ "/foo/bar", "/bar" ] ) )
		script["set"]["filter"].setInput( script["barFilter"]["out"] )

		script["instancer"]["prototypes"].setInput( script["set"]["out"] )

		script["instancer"]["prototypeMode"].setValue( GafferScene.Instancer.PrototypeMode.IndexedRootsList )
		script["instancer"]["prototypeRootsList"].setValue( IECore.StringVectorData( [ "/foo/bar", "/bar" ] ) )

		self.assertEqual(
			script["instancer"]["out"]["setNames"].getValue(),
			IECore.InternedStringVectorData( [ "sphereSet", "cubeSet", "barSet" ] )
		)

		self.assertEqual(
			set( script["instancer"]["out"].set( "sphereSet" ).value.paths() ),
			{
				"/object/instances/bar/0/sphere",
				"/object/instances/bar/3/sphere",
			}
		)

		self.assertEqual(
			set( script["instancer"]["out"].set( "cubeSet" ).value.paths() ),
			{
				"/object/instances/bar1/1/baz/cube",
				"/object/instances/bar1/2/baz/cube",
			}
		)

		self.assertEqual(
			set( script["instancer"]["out"].set( "barSet" ).value.paths() ),
			{
				"/object/instances/bar/0",
				"/object/instances/bar/3",
				"/object/instances/bar1/1",
				"/object/instances/bar1/2",
			}
		)

	def testIds( self ) :

		points = IECoreScene.PointsPrimitive( IECore.V3fVectorData( [ imath.V3f( x, 0, 0 ) for x in range( 0, 4 ) ] ) )
		points["id"] = IECoreScene.PrimitiveVariable(
			IECoreScene.PrimitiveVariable.Interpolation.Vertex,
			IECore.IntVectorData( [ 10, 100, 111, 5 ] ),
		)
		points["index"] = IECoreScene.PrimitiveVariable(
			IECoreScene.PrimitiveVariable.Interpolation.Vertex,
			IECore.IntVectorData( [ 0, 1, 0, 1 ] ),
		)

		objectToScene = GafferScene.ObjectToScene()
		objectToScene["object"].setValue( points )

		sphere = GafferScene.Sphere()
		cube = GafferScene.Cube()
		instances = GafferScene.Parent()
		instances["in"].setInput( sphere["out"] )
		instances["children"][0].setInput( cube["out"] )
		instances["parent"].setValue( "/" )

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( objectToScene["out"] )
		instancer["prototypes"].setInput( instances["out"] )
		instancer["parent"].setValue( "/object" )
		instancer["prototypeIndex"].setValue( "index" )
		instancer["id"].setValue( "id" )

		self.assertEqual( instancer["out"].childNames( "/object/instances" ), IECore.InternedStringVectorData( [ "sphere", "cube" ] ) )
		self.assertEqual( instancer["out"].childNames( "/object/instances/sphere" ), IECore.InternedStringVectorData( [ "10", "111" ] ) )
		self.assertEqual( instancer["out"].childNames( "/object/instances/cube" ), IECore.InternedStringVectorData( [ "5", "100" ] ) )
		self.assertEqual( instancer["out"].childNames( "/object/instances/sphere/10" ), IECore.InternedStringVectorData() )
		self.assertEqual( instancer["out"].childNames( "/object/instances/sphere/111" ), IECore.InternedStringVectorData() )
		self.assertEqual( instancer["out"].childNames( "/object/instances/cube/100" ), IECore.InternedStringVectorData() )
		self.assertEqual( instancer["out"].childNames( "/object/instances/cube/5" ), IECore.InternedStringVectorData() )

		self.assertEqual( instancer["out"].object( "/object/instances" ), IECore.NullObject.defaultNullObject() )
		self.assertEqual( instancer["out"].object( "/object/instances/sphere" ), IECore.NullObject.defaultNullObject() )
		self.assertEqual( instancer["out"].object( "/object/instances/cube" ), IECore.NullObject.defaultNullObject() )
		self.assertEqual( instancer["out"].object( "/object/instances/sphere/10" ), sphere["out"].object( "/sphere" ) )
		self.assertEqual( instancer["out"].object( "/object/instances/sphere/111" ), sphere["out"].object( "/sphere" ) )
		self.assertEqual( instancer["out"].object( "/object/instances/cube/100" ), cube["out"].object( "/cube" ) )
		self.assertEqual( instancer["out"].object( "/object/instances/cube/5" ), cube["out"].object( "/cube" ) )

		self.assertEqual( instancer["out"].transform( "/object/instances" ), imath.M44f() )
		self.assertEqual( instancer["out"].transform( "/object/instances/sphere" ), imath.M44f() )
		self.assertEqual( instancer["out"].transform( "/object/instances/cube" ), imath.M44f() )
		self.assertEqual( instancer["out"].transform( "/object/instances/sphere/10" ), imath.M44f() )
		self.assertEqual( instancer["out"].transform( "/object/instances/sphere/111" ), imath.M44f().translate( imath.V3f( 2, 0, 0 ) ) )
		self.assertEqual( instancer["out"].transform( "/object/instances/cube/100" ), imath.M44f().translate( imath.V3f( 1, 0, 0 ) ) )
		self.assertEqual( instancer["out"].transform( "/object/instances/cube/5" ), imath.M44f().translate( imath.V3f( 3, 0, 0 ) ) )

		self.assertRaisesRegex(
			Gaffer.ProcessException,
			'Instancer.out.transform : Instance id "77" is invalid.  Topology may have changed during shutter.',
			instancer["out"].transform, "/object/instances/cube/77"
		)

		self.assertSceneValid( instancer["out"] )

	def testNegativeIdsAndIndices( self ) :

		points = IECoreScene.PointsPrimitive( IECore.V3fVectorData( [ imath.V3f( x, 0, 0 ) for x in range( 0, 2 ) ] ) )
		points["id"] = IECoreScene.PrimitiveVariable(
			IECoreScene.PrimitiveVariable.Interpolation.Vertex,
			IECore.IntVectorData( [ -10, -5 ] ),
		)
		points["index"] = IECoreScene.PrimitiveVariable(
			IECoreScene.PrimitiveVariable.Interpolation.Vertex,
			IECore.IntVectorData( [ -1, -2 ] ),
		)

		objectToScene = GafferScene.ObjectToScene()
		objectToScene["object"].setValue( points )

		sphere = GafferScene.Sphere()
		cube = GafferScene.Cube()
		instances = GafferScene.Parent()
		instances["in"].setInput( sphere["out"] )
		instances["children"][0].setInput( cube["out"] )
		instances["parent"].setValue( "/" )

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( objectToScene["out"] )
		instancer["prototypes"].setInput( instances["out"] )
		instancer["parent"].setValue( "/object" )
		instancer["prototypeIndex"].setValue( "index" )
		instancer["id"].setValue( "id" )

		self.assertEqual( instancer["out"].childNames( "/object/instances" ), IECore.InternedStringVectorData( [ "sphere", "cube" ] ) )
		self.assertEqual( instancer["out"].childNames( "/object/instances/sphere" ), IECore.InternedStringVectorData( [ "-5" ] ) )
		self.assertEqual( instancer["out"].childNames( "/object/instances/cube" ), IECore.InternedStringVectorData( [ "-10" ] ) )
		self.assertEqual( instancer["out"].childNames( "/object/instances/sphere/-5" ), IECore.InternedStringVectorData() )
		self.assertEqual( instancer["out"].childNames( "/object/instances/cube/-10" ), IECore.InternedStringVectorData() )

		self.assertEqual( instancer["out"].object( "/object/instances" ), IECore.NullObject.defaultNullObject() )
		self.assertEqual( instancer["out"].object( "/object/instances/sphere" ), IECore.NullObject.defaultNullObject() )
		self.assertEqual( instancer["out"].object( "/object/instances/cube" ), IECore.NullObject.defaultNullObject() )
		self.assertEqual( instancer["out"].object( "/object/instances/sphere/-5" ), sphere["out"].object( "/sphere" ) )
		self.assertEqual( instancer["out"].object( "/object/instances/cube/-10" ), cube["out"].object( "/cube" ) )

		self.assertSceneValid( instancer["out"] )

	def testDuplicateIds( self ) :

		points = IECoreScene.PointsPrimitive( IECore.V3fVectorData( [ imath.V3f( x, 0, 0 ) for x in range( 6 ) ] ) )
		points["id"] = IECoreScene.PrimitiveVariable(
			IECoreScene.PrimitiveVariable.Interpolation.Vertex,
			IECore.IntVectorData( [ 0, 0, 2, 2, 4, 4 ] ),
		)

		objectToScene = GafferScene.ObjectToScene()
		objectToScene["object"].setValue( points )

		sphere = GafferScene.Sphere()

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( objectToScene["out"] )
		instancer["prototypes"].setInput( sphere["out"] )
		instancer["parent"].setValue( "/object" )
		instancer["id"].setValue( "id" )

		self.assertSceneValid( instancer["out"] )

		self.assertEqual( instancer["out"].childNames( "/object/instances/sphere" ), IECore.InternedStringVectorData( [ "0", "2", "4" ] ) )

		self.assertEqual( instancer["out"].transform( "/object/instances/sphere/0" ), imath.M44f().translate( imath.V3f( 0, 0, 0 ) ) )
		self.assertEqual( instancer["out"].transform( "/object/instances/sphere/2" ), imath.M44f().translate( imath.V3f( 2, 0, 0 ) ) )
		self.assertEqual( instancer["out"].transform( "/object/instances/sphere/4" ), imath.M44f().translate( imath.V3f( 4, 0, 0 ) ) )


	def testAttributes( self ) :

		points = IECoreScene.PointsPrimitive( IECore.V3fVectorData( [ imath.V3f( x, 0, 0 ) for x in range( 0, 2 ) ] ) )
		points["testFloat"] = IECoreScene.PrimitiveVariable(
			IECoreScene.PrimitiveVariable.Interpolation.Vertex,
			IECore.FloatVectorData( [ 0, 1 ] ),
		)
		points["testColor"] = IECoreScene.PrimitiveVariable(
			IECoreScene.PrimitiveVariable.Interpolation.Vertex,
			IECore.Color3fVectorData( [ imath.Color3f( 1, 0, 0 ), imath.Color3f( 0, 1, 0 ) ] ),
		)
		points["testPoint"] = IECoreScene.PrimitiveVariable(
			IECoreScene.PrimitiveVariable.Interpolation.Vertex,
			IECore.V3fVectorData(
				[ imath.V3f( 0, 0, 0 ), imath.V3f( 1, 1, 1 ) ],
				IECore.GeometricData.Interpretation.Point
			),
		)

		objectToScene = GafferScene.ObjectToScene()
		objectToScene["object"].setValue( points )

		sphere = GafferScene.Sphere()

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( objectToScene["out"] )
		instancer["prototypes"].setInput( sphere["out"] )
		instancer["parent"].setValue( "/object" )

		self.assertEqual(
			instancer["out"].attributes( "/object/instances" ),
			IECore.CompoundObject()
		)

		self.assertEqual(
			instancer["out"].attributes( "/object/instances/sphere" ),
			IECore.CompoundObject()
		)

		self.assertEqual(
			instancer["out"].attributes( "/object/instances/sphere/0" ),
			IECore.CompoundObject()
		)

		instancer["attributes"].setValue( "testFloat testColor testPoint" )

		self.assertEqual(
			instancer["out"].attributes( "/object/instances/sphere/0" ),
			IECore.CompoundObject( {
				"testFloat" : IECore.FloatData( 0.0 ),
				"testColor" : IECore.Color3fData( imath.Color3f( 1, 0, 0 ) ),
				"testPoint" : IECore.V3fData(
					imath.V3f( 0 ),
					IECore.GeometricData.Interpretation.Point
				)
			} )
		)

		self.assertEqual(
			instancer["out"].attributes( "/object/instances/sphere/1" ),
			IECore.CompoundObject( {
				"testFloat" : IECore.FloatData( 1.0 ),
				"testColor" : IECore.Color3fData( imath.Color3f( 0, 1, 0 ) ),
				"testPoint" : IECore.V3fData(
					imath.V3f( 1 ),
					IECore.GeometricData.Interpretation.Point
				)
			} )
		)

		instancer["attributePrefix"].setValue( "user:" )

		self.assertEqual(
			instancer["out"].attributes( "/object/instances/sphere/0" ),
			IECore.CompoundObject( {
				"user:testFloat" : IECore.FloatData( 0.0 ),
				"user:testColor" : IECore.Color3fData( imath.Color3f( 1, 0, 0 ) ),
				"user:testPoint" : IECore.V3fData(
					imath.V3f( 0 ),
					IECore.GeometricData.Interpretation.Point
				)
			} )
		)

		self.assertEqual(
			instancer["out"].attributes( "/object/instances/sphere/1" ),
			IECore.CompoundObject( {
				"user:testFloat" : IECore.FloatData( 1.0 ),
				"user:testColor" : IECore.Color3fData( imath.Color3f( 0, 1, 0 ) ),
				"user:testPoint" : IECore.V3fData(
					imath.V3f( 1 ),
					IECore.GeometricData.Interpretation.Point
				)
			} )
		)

		instancer["attributePrefix"].setValue( "foo:" )

		self.assertEqual(
			instancer["out"].attributes( "/object/instances/sphere/0" ),
			IECore.CompoundObject( {
				"foo:testFloat" : IECore.FloatData( 0.0 ),
				"foo:testColor" : IECore.Color3fData( imath.Color3f( 1, 0, 0 ) ),
				"foo:testPoint" : IECore.V3fData(
					imath.V3f( 0 ),
					IECore.GeometricData.Interpretation.Point
				)
			} )
		)

		self.assertEqual(
			instancer["out"].attributes( "/object/instances/sphere/1" ),
			IECore.CompoundObject( {
				"foo:testFloat" : IECore.FloatData( 1.0 ),
				"foo:testColor" : IECore.Color3fData( imath.Color3f( 0, 1, 0 ) ),
				"foo:testPoint" : IECore.V3fData(
					imath.V3f( 1 ),
					IECore.GeometricData.Interpretation.Point
				)
			} )
		)

	def testEmptyAttributesHaveConstantHash( self ) :

		points = IECoreScene.PointsPrimitive( IECore.V3fVectorData( [ imath.V3f( x, 0, 0 ) for x in range( 0, 2 ) ] ) )
		objectToScene = GafferScene.ObjectToScene()
		objectToScene["object"].setValue( points )

		sphere = GafferScene.Sphere()

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( objectToScene["out"] )
		instancer["prototypes"].setInput( sphere["out"] )
		instancer["parent"].setValue( "/object" )

		self.assertEqual(
			instancer["out"].attributesHash( "/object/instances/sphere/0" ),
			instancer["out"].attributesHash( "/object/instances/sphere/1" ),
		)

		self.assertEqual(
			instancer["out"].attributes( "/object/instances/sphere/0" ),
			instancer["out"].attributes( "/object/instances/sphere/1" ),
		)

	def testEditAttributes( self ) :

		points = IECoreScene.PointsPrimitive( IECore.V3fVectorData( [ imath.V3f( x, 0, 0 ) for x in range( 0, 2 ) ] ) )
		points["testFloat"] = IECoreScene.PrimitiveVariable(
			IECoreScene.PrimitiveVariable.Interpolation.Vertex,
			IECore.FloatVectorData( [ 0, 1 ] ),
		)

		objectToScene = GafferScene.ObjectToScene()
		objectToScene["object"].setValue( points )

		sphere = GafferScene.Sphere()

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( objectToScene["out"] )
		instancer["prototypes"].setInput( sphere["out"] )
		instancer["parent"].setValue( "/object" )

		instancer["attributes"].setValue( "test*" )

		self.assertEqual(
			instancer["out"].attributes( "/object/instances/sphere/0" ),
			IECore.CompoundObject( {
				"testFloat" : IECore.FloatData( 0.0 ),
			} )
		)

		self.assertEqual(
			instancer["out"].attributes( "/object/instances/sphere/1" ),
			IECore.CompoundObject( {
				"testFloat" : IECore.FloatData( 1.0 ),
			} )
		)

		points["testFloat"] = IECoreScene.PrimitiveVariable(
			IECoreScene.PrimitiveVariable.Interpolation.Vertex,
			IECore.FloatVectorData( [ 1, 2 ] ),
		)
		objectToScene["object"].setValue( points )

		self.assertEqual(
			instancer["out"].attributes( "/object/instances/sphere/0" ),
			IECore.CompoundObject( {
				"testFloat" : IECore.FloatData( 1.0 ),
			} )
		)

		self.assertEqual(
			instancer["out"].attributes( "/object/instances/sphere/1" ),
			IECore.CompoundObject( {
				"testFloat" : IECore.FloatData( 2.0 ),
			} )
		)

	def testPrototypeAttributes( self ) :

		script = self.buildPrototypeRootsScript()
		# add some attributes throughout the prototype hierarchies
		script["attrFilter"] = GafferScene.PathFilter()
		script["attrFilter"]["paths"].setValue( IECore.StringVectorData( [ "/foo", "/foo/bar", "/bar", "/bar/baz/cube" ] ) )
		script["attributes"] = GafferScene.StandardAttributes()
		script["attributes"]["in"].setInput( script["instancer"]["prototypes"].getInput() )
		script["attributes"]["filter"].setInput( script["attrFilter"]["out"] )
		script["attributes"]["attributes"]["deformationBlur"]["enabled"].setValue( True )
		script["attrSpreadsheet"] = Gaffer.Spreadsheet()
		script["attrSpreadsheet"]["selector"].setValue( "${scene:path}" )
		script["attrSpreadsheet"]["rows"].addColumn( script["attributes"]["attributes"]["deformationBlur"]["value"] )
		script["attributes"]["attributes"]["deformationBlur"]["value"].setInput( script["attrSpreadsheet"]["out"][0] )
		for location, value in ( ( "/foo", False ), ( "/foo/bar", True ), ( "/bar", True ), ( "/bar/baz/cube", False ) ) :
			row = script["attrSpreadsheet"]["rows"].addRow()
			row["name"].setValue( location )
			row["cells"][0]["value"].setValue( value )
		script["instancer"]["prototypes"].setInput( script["attributes"]["out"] )

		script["instancer"]["prototypeMode"].setValue( GafferScene.Instancer.PrototypeMode.IndexedRootsList )
		script["instancer"]["prototypeRootsList"].setValue( IECore.StringVectorData( [ "/foo", "/bar" ] ) )

		self.assertEqual( script["instancer"]["out"].attributes( "/object/instances" ), IECore.CompoundObject() )
		self.assertEqual( script["instancer"]["out"].attributes( "/object/instances/foo" ), IECore.CompoundObject() )
		self.assertEqual( script["instancer"]["out"].attributes( "/object/instances/bar" ), IECore.CompoundObject() )

		for i in [ "0", "3" ] :

			self.assertEqual( script["instancer"]["out"].attributes( "/object/instances/foo/{i}".format( i=i ) )["gaffer:deformationBlur"].value, False )
			self.assertEqual( script["instancer"]["out"].fullAttributes( "/object/instances/foo/{i}".format( i=i ) )["gaffer:deformationBlur"].value, False )
			self.assertEqual( script["instancer"]["out"].attributes( "/object/instances/foo/{i}/bar".format( i=i ) )["gaffer:deformationBlur"].value, True )
			self.assertEqual( script["instancer"]["out"].attributes( "/object/instances/foo/{i}/bar/sphere" ), IECore.CompoundObject() )
			self.assertEqual( script["instancer"]["out"].fullAttributes( "/object/instances/foo/{i}/bar/sphere".format( i=i ) )["gaffer:deformationBlur"].value, True )

		for i in [ "1", "2" ] :

			self.assertEqual( script["instancer"]["out"].attributes( "/object/instances/bar/{i}".format( i=i ) )["gaffer:deformationBlur"].value, True )
			self.assertEqual( script["instancer"]["out"].fullAttributes( "/object/instances/bar/{i}".format( i=i ) )["gaffer:deformationBlur"].value, True )
			self.assertEqual( script["instancer"]["out"].attributes( "/object/instances/bar/{i}/baz".format( i=i ) ), IECore.CompoundObject() )
			self.assertEqual( script["instancer"]["out"].fullAttributes( "/object/instances/bar/{i}/baz".format( i=i ) )["gaffer:deformationBlur"].value, True )
			self.assertEqual( script["instancer"]["out"].attributes( "/object/instances/bar/{i}/baz/cube".format( i=i ) )["gaffer:deformationBlur"].value, False )

		self.assertSceneValid( script["instancer"]["out"] )

	def testUnconnectedInstanceInput( self ) :

		plane = GafferScene.Plane()
		plane["sets"].setValue( "A" )
		plane["divisions"].setValue( imath.V2i( 1, 500 ) )

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( plane["out"] )
		instancer["parent"].setValue( "/plane" )

		self.assertEqual( instancer["out"].set( "A" ).value.paths(), [ "/plane" ] )

	def testDirtyPropagation( self ) :

		plane = GafferScene.Plane()
		instancer = GafferScene.Instancer()
		instancer["in"].setInput( plane["out"] )
		instancer["prototypes"].setInput( plane["out"] )

		cs = GafferTest.CapturingSlot( instancer.plugDirtiedSignal() )
		instancer["parent"].setValue( "plane" )
		self.assertIn( instancer["out"]["childNames"], { x[0] for x in cs } )

		del cs[:]
		filter = GafferScene.PathFilter()
		instancer["filter"].setInput( filter["out"] )
		self.assertIn( instancer["out"]["childNames"], { x[0] for x in cs } )

	def testNoPrimitiveAtParent( self ) :

		group = GafferScene.Group()

		sphere = GafferScene.Sphere()
		sphere["sets"].setValue( "setA" )

		groupFilter = GafferScene.PathFilter()
		groupFilter["paths"].setValue( IECore.StringVectorData( [ "/group" ] ) )

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( group["out"] )
		instancer["prototypes"].setInput( sphere["out"] )
		instancer["filter"].setInput( groupFilter["out"] )

		self.assertSceneValid( instancer["out"] )
		self.assertEqual( instancer["out"].childNames( "/group/instances" ) , IECore.InternedStringVectorData() )
		self.assertEqual( instancer["out"].set( "setA" ) , IECore.PathMatcherData() )

	def testSetPassThroughs( self ) :

		# If the prototypes don't provide a set, then we should do a perfect
		# pass through.

		plane = GafferScene.Plane()
		plane["sets"].setValue( "A" )

		planeFilter = GafferScene.PathFilter()
		planeFilter["paths"].setValue( IECore.StringVectorData( [ "/plane" ] ) )

		sphere = GafferScene.Sphere()

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( plane["out"] )
		instancer["prototypes"].setInput( sphere["out"] )
		instancer["filter"].setInput( planeFilter["out"] )

		self.assertTrue( instancer["out"].exists( "/plane/instances/sphere/0" ) )
		self.assertEqual( instancer["out"].setHash( "A" ), instancer["in"].setHash( "A" ) )
		self.assertEqual( instancer["out"].set( "A" ), instancer["in"].set( "A" ) )
		self.assertEqual( instancer["out"].set( "A" ).value.paths(), [ "/plane" ] )

	def testContexts( self ):

		points = IECoreScene.PointsPrimitive(
					IECore.V3fVectorData(
						[ imath.V3f( i, 0, 0 ) for i in range( 100 ) ]
					)
				)

		points["floatVar"] = IECoreScene.PrimitiveVariable( IECoreScene.PrimitiveVariable.Interpolation.Vertex, IECore.FloatVectorData(
						[ 2 * math.sin( i ) for i in range( 100 ) ]
					) )
		points["vectorVar"] = IECoreScene.PrimitiveVariable( IECoreScene.PrimitiveVariable.Interpolation.Vertex, IECore.V3fVectorData(
						[ imath.V3f( i + 2, i + 3, i + 4 ) for i in range( 100 ) ]
					) )
		points["uvVar"] = IECoreScene.PrimitiveVariable( IECoreScene.PrimitiveVariable.Interpolation.Vertex, IECore.V2fVectorData(
						[ imath.V2f( i * 0.01, i * 0.02 ) for i in range( 100 ) ]
					) )
		points["intVar"] = IECoreScene.PrimitiveVariable( IECoreScene.PrimitiveVariable.Interpolation.Vertex, IECore.IntVectorData(
						[ i for i in range( 100 ) ]
					) )
		points["colorVar"] = IECoreScene.PrimitiveVariable( IECoreScene.PrimitiveVariable.Interpolation.Vertex, IECore.Color3fVectorData(
						[ imath.Color3f( i * 0.1 + 2, i * 0.1 + 3, i * 0.1 + 4 ) for i in range( 100 ) ]
					) )
		points["color4fVar"] = IECoreScene.PrimitiveVariable( IECoreScene.PrimitiveVariable.Interpolation.Vertex, IECore.Color4fVectorData(
						[ imath.Color4f( i * 0.1 + 2, i * 0.1 + 3, i * 0.1 + 4, i * 0.1 + 5 ) for i in range( 100 ) ]
					) )
		points["stringVar"] = IECoreScene.PrimitiveVariable( IECoreScene.PrimitiveVariable.Interpolation.Vertex, IECore.StringVectorData(
						[ "foo%i"%(i//34) for i in range( 100 ) ]
					) )
		points["unindexedRoots"] = IECoreScene.PrimitiveVariable( IECoreScene.PrimitiveVariable.Interpolation.Vertex, IECore.StringVectorData(
						[ ["cube","plane","sphere"][i//34] for i in range( 100 ) ]
					) )
		points["indexedRoots"] = IECoreScene.PrimitiveVariable( IECoreScene.PrimitiveVariable.Interpolation.Vertex,
			IECore.StringVectorData( [ "cube","plane","sphere"] ),
			IECore.IntVectorData( [(i//34) for i in range( 100 )] ),
		)
		pointsSource = GafferScene.ObjectToScene()
		pointsSource["name"].setValue( "points" )
		pointsSource["object"].setValue( points )

		attributeSphere = GafferScene.Sphere()

		sphereFilter = GafferScene.PathFilter()
		sphereFilter["paths"].setValue( IECore.StringVectorData( [ '/sphere' ] ) )

		# In any practical situation where we just needed to set up attributes, we could use the "attributes"
		# plug to set them up more cheaply.  But for testing, setting up attributes is simpler than any realistic
		# test
		customAttributes = GafferScene.CustomAttributes()
		customAttributes["in"].setInput( attributeSphere["out"] )
		customAttributes["filter"].setInput( sphereFilter["out"] )
		customAttributes["attributes"].addChild( Gaffer.NameValuePlug( "floatAttr", Gaffer.FloatPlug( "value", flags = Gaffer.Plug.Flags.Default | Gaffer.Plug.Flags.Dynamic ), True, "member1" ) )
		customAttributes["attributes"].addChild( Gaffer.NameValuePlug( "vectorAttr", Gaffer.V3fPlug( "value", flags = Gaffer.Plug.Flags.Default | Gaffer.Plug.Flags.Dynamic ), True, "member2" ) )
		customAttributes["attributes"].addChild( Gaffer.NameValuePlug( "uvAttr", Gaffer.V2fPlug( "value", flags = Gaffer.Plug.Flags.Default | Gaffer.Plug.Flags.Dynamic ), True, "member3" ) )
		customAttributes["attributes"].addChild( Gaffer.NameValuePlug( "intAttr", Gaffer.IntPlug( "value", flags = Gaffer.Plug.Flags.Default | Gaffer.Plug.Flags.Dynamic, ), True, "member4" ) )
		customAttributes["attributes"].addChild( Gaffer.NameValuePlug( "colorAttr", Gaffer.Color3fPlug( "value", flags = Gaffer.Plug.Flags.Default | Gaffer.Plug.Flags.Dynamic ), True, "member5" ) )
		customAttributes["attributes"].addChild( Gaffer.NameValuePlug( "color4fAttr", Gaffer.Color4fPlug( "value", flags = Gaffer.Plug.Flags.Default | Gaffer.Plug.Flags.Dynamic ), True, "member6" ) )
		customAttributes["attributes"].addChild( Gaffer.NameValuePlug( "stringAttr", Gaffer.StringPlug( "value", flags = Gaffer.Plug.Flags.Default | Gaffer.Plug.Flags.Dynamic ), True, "member7" ) )
		customAttributes["attributes"].addChild( Gaffer.NameValuePlug( "seedAttr", Gaffer.IntPlug( "value", flags = Gaffer.Plug.Flags.Default | Gaffer.Plug.Flags.Dynamic, ), True, "member8" ) )
		customAttributes["attributes"].addChild( Gaffer.NameValuePlug( "frameAttr", Gaffer.FloatPlug( "value", flags = Gaffer.Plug.Flags.Default | Gaffer.Plug.Flags.Dynamic, ), True, "member9" ) )

		customAttributes["ReadContextExpression"] = Gaffer.Expression()
		customAttributes["ReadContextExpression"].setExpression( inspect.cleandoc(
			"""
			parent["attributes"]["member1"]["value"] = context.get( "floatVar", -1 )
			parent["attributes"]["member2"]["value"] = context.get( "vectorVar", imath.V3f(-1) )
			parent["attributes"]["member3"]["value"] = context.get( "uvVar", imath.V2f(-1) )
			parent["attributes"]["member4"]["value"] = context.get( "intVar", -1 )
			parent["attributes"]["member5"]["value"] = context.get( "colorVar", imath.Color3f( -1 ) )
			parent["attributes"]["member6"]["value"] = context.get( "color4fVar", imath.Color4f( -1 ) )
			parent["attributes"]["member7"]["value"] = context.get( "stringVar", "" )
			parent["attributes"]["member8"]["value"] = context.get( "seed", -1 )
			parent["attributes"]["member9"]["value"] = context.get( "frame", -1 )
			"""
		) )

		group = GafferScene.Group()
		group["in"][0].setInput( customAttributes["out"] )
		group["name"].setValue( 'withAttrs' )

		cube = GafferScene.Cube()
		plane = GafferScene.Plane()
		sphere = GafferScene.Sphere()

		parent = GafferScene.Parent()
		parent["parent"].setValue( '/' )
		parent["in"].setInput( group["out"] )
		parent["children"][0].setInput( cube["out"] )
		parent["children"][1].setInput( plane["out"] )
		parent["children"][2].setInput( sphere["out"] )

		pointsFilter = GafferScene.PathFilter()
		pointsFilter["paths"].setValue( IECore.StringVectorData( [ '/points' ] ) )

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( pointsSource["out"] )
		instancer["filter"].setInput( pointsFilter["out"] )
		instancer["prototypes"].setInput( parent["out"] )

		def uniqueCounts():
			return dict( [ (i[0], i[1].value) for i in instancer["variations"].getValue().items() ] )

		def childNameStrings( location ):
			return [ i.value() for i in instancer['out'].childNames( location ) ]

		def testAttributes( **expected ):
			a = [ instancer['out'].attributes( "points/instances/withAttrs/" + i.value() + "/sphere" ) for i in instancer['out'].childNames( "points/instances/withAttrs" ) ]
			r = {}
			for n in a[0].keys():
				r = [ i[n].value for i in a]
				if n + "_seedCount" in expected:
					self.assertEqual( len( set( r ) ), expected[ n + "_seedCount" ] )
				elif n in expected:
					self.assertEqual( len(r), len(expected[n]) )
					if type( r[0] ) == float:
						if r != expected[n]:
							for i in range( len( r ) ):
								self.assertAlmostEqual( r[i], expected[n][i], places = 6 )
					else:
						self.assertEqual( r, expected[n] )
				else:
					if type( r[0] ) == str:
						self.assertEqual( r, [""] * len( r ) )
					else:
						self.assertEqual( r, [type( r[0] )( -1 )] * len( r ) )

		# Compatible with C++ rounding
		def compatRound( x ):
			if x >= 0.0:
				return math.floor(x + 0.5)
			else:
				return math.ceil(x - 0.5)

		def quant( x, q ):
			return compatRound( float( x ) / q ) * q

		self.assertEqual( uniqueCounts(), { "" : 1 } )
		self.assertEqual( childNameStrings( "points/instances" ), [ "withAttrs", "cube", "plane", "sphere" ] )
		self.assertEqual( childNameStrings( "points/instances/withAttrs" ), [ str(i) for i in range( 100 ) ] )
		self.assertEqual( childNameStrings( "points/instances/cube" ), [] )
		self.assertEqual( childNameStrings( "points/instances/plane" ), [] )
		self.assertEqual( childNameStrings( "points/instances/sphere" ), [] )

		instancer["prototypeMode"].setValue( GafferScene.Instancer.PrototypeMode.RootPerVertex )
		instancer["prototypeRoots"].setValue( "indexedRoots" )
		self.assertEqual( uniqueCounts(), { "" : 3 } )
		self.assertEqual( childNameStrings( "points/instances/cube" ), [ str(i) for i in range( 0, 34 ) ] )
		self.assertEqual( childNameStrings( "points/instances/plane" ), [ str(i) for i in range( 34, 68 ) ] )
		self.assertEqual( childNameStrings( "points/instances/sphere" ), [ str(i) for i in range( 68, 100 ) ] )

		instancer["prototypeRoots"].setValue( "unindexedRoots" )
		"""
		# How things should work
		self.assertEqual( uniqueCounts(), { "" : 3 } )
		self.assertEqual( childNameStrings( "points/instances/cube" ), [ str(i) for i in range( 0, 34 ) ] )
		self.assertEqual( childNameStrings( "points/instances/plane" ), [ str(i) for i in range( 34, 68 ) ] )
		self.assertEqual( childNameStrings( "points/instances/sphere" ), [ str(i) for i in range( 68, 100 ) ] )
		"""
		# How things currently work
		self.assertEqual( uniqueCounts(), { "" : 1 } )
		self.assertEqual( childNameStrings( "points/instances/cube" ), [ str(i) for i in range( 100 ) ] )
		self.assertEqual( childNameStrings( "points/instances/plane" ), [] )
		self.assertEqual( childNameStrings( "points/instances/sphere" ), [] )

		instancer["prototypeMode"].setValue( GafferScene.Instancer.PrototypeMode.IndexedRootsList )
		instancer["prototypeIndex"].setValue( 'intVar' )

		self.assertEqual( uniqueCounts(), { "" : 4 } )
		self.assertEqual( childNameStrings( "points/instances/withAttrs" ), [ str(i) for i in range( 0, 100, 4 ) ] )
		self.assertEqual( childNameStrings( "points/instances/cube" ), [ str(i) for i in range( 1, 100, 4 ) ] )
		self.assertEqual( childNameStrings( "points/instances/plane" ), [ str(i) for i in range( 2, 100, 4 ) ] )
		self.assertEqual( childNameStrings( "points/instances/sphere" ), [ str(i) for i in range( 3, 100, 4 ) ] )

		# No context overrides yet
		testAttributes( frameAttr = [ 1 ] * 25 )

		instancer["contextVariables"].addChild( GafferScene.Instancer.ContextVariablePlug( "context" ) )
		instancer["contextVariables"][0]["name"].setValue( "floatVar" )
		instancer["contextVariables"][0]["quantize"].setValue( 0 )

		# With zero quantization, everything is now unique
		testAttributes( frameAttr = [ 1 ] * 25, floatAttr = [ 2 * math.sin( i ) for i in range(0, 100, 4) ] )
		# Check both the global unique count, and the per-context variable unique counts
		self.assertEqual( uniqueCounts(), { "" : 100, "floatVar" : 100 } )

		# With massive quantization, all values collapse
		instancer["contextVariables"][0]["quantize"].setValue( 100 )
		testAttributes( frameAttr = [ 1 ] * 25, floatAttr = [ 0 for i in range(0, 100, 4) ] )
		self.assertEqual( uniqueCounts(), { "" : 4, "floatVar" : 1 } )

		# With moderate quantization, we can see how different prototypes combine with the contexts to produce
		# more unique values
		instancer["contextVariables"][0]["quantize"].setValue( 1 )
		floatExpected = [ compatRound( 2 * math.sin( i ) ) for i in range(0, 100, 4) ]
		testAttributes( frameAttr = [ 1 ] * 25, floatAttr = floatExpected )
		self.assertEqual( uniqueCounts(), { "" : 20, "floatVar" : 5 } )

		instancer["prototypeRootsList"].setValue( IECore.StringVectorData( [ "withAttrs", "cube", "plane", "sphere" ] ) )
		testAttributes( frameAttr = [ 1 ] * 25, floatAttr = floatExpected )
		self.assertEqual( uniqueCounts(), { "" : 20, "floatVar" : 5 } )

		# Test an empty root
		instancer["prototypeRootsList"].setValue( IECore.StringVectorData( [ "withAttrs", "", "plane", "sphere" ] ) )
		self.assertEqual( uniqueCounts(), { "" : 15, "floatVar" : 5 } )

		# Now lets just focus on context variation
		instancer["prototypeRootsList"].setValue( IECore.StringVectorData( [] ) )
		instancer["prototypeIndex"].setValue( '' )
		floatExpected = [ compatRound( 2 * math.sin( i ) ) for i in range(0, 100) ]
		testAttributes( frameAttr = [ 1 ] * 100, floatAttr = floatExpected )
		self.assertEqual( uniqueCounts(), { "" : 5, "floatVar" : 5 } )

		# Add a second context variation
		instancer["contextVariables"].addChild( GafferScene.Instancer.ContextVariablePlug( "context" ) )
		instancer["contextVariables"][1]["name"].setValue( "vectorVar" )
		instancer["contextVariables"][1]["quantize"].setValue( 0 )

		testAttributes( frameAttr = [ 1 ] * 100, floatAttr = floatExpected,
			vectorAttr = [ imath.V3f( i + 2, i + 3, i + 4 ) for i in range(0, 100) ]
		)
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "vectorVar" : 100, "" : 100 } )

		instancer["contextVariables"][1]["quantize"].setValue( 10 )
		testAttributes( frameAttr = [ 1 ] * 100, floatAttr = floatExpected,
			vectorAttr = [ imath.V3f( quant( i + 2, 10 ), quant( i + 3, 10 ), quant( i + 4, 10 ) ) for i in range(0, 100) ]
		)
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "vectorVar" : 31, "" : 64 } )

		# Try all the different types
		instancer["contextVariables"][1]["name"].setValue( "uvVar" )
		instancer["contextVariables"][1]["quantize"].setValue( 0 )

		testAttributes( frameAttr = [ 1 ] * 100, floatAttr = floatExpected,
			uvAttr = [ imath.V2f( i * 0.01, i * 0.02 ) for i in range(0, 100) ]
		)
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "uvVar" : 100, "" : 100 } )

		instancer["contextVariables"][1]["quantize"].setValue( 1 )
		testAttributes( frameAttr = [ 1 ] * 100, floatAttr = floatExpected,
			uvAttr = [ imath.V2f( compatRound( i * 0.01 ), compatRound( i * 0.02 ) ) for i in range(0, 100) ]
		)
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "uvVar" : 4, "" : 20 } )


		instancer["contextVariables"][1]["name"].setValue( "intVar" )
		instancer["contextVariables"][1]["quantize"].setValue( 0 )

		testAttributes( frameAttr = [ 1 ] * 100, floatAttr = floatExpected,
			intAttr = [ i for i in range(0, 100) ]
		)
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "intVar" : 100, "" : 100 } )

		instancer["contextVariables"][1]["quantize"].setValue( 10 )
		testAttributes( frameAttr = [ 1 ] * 100, floatAttr = floatExpected,
			intAttr = [ quant( i, 10 ) for i in range(0, 100) ]
		)
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "intVar" : 11, "" : 48 } )


		instancer["contextVariables"][1]["name"].setValue( "stringVar" )
		instancer["contextVariables"][1]["quantize"].setValue( 0 )

		testAttributes( frameAttr = [ 1 ] * 100, floatAttr = floatExpected,
			stringAttr = [ "foo%i" % ( i / 34 ) for i in range(100) ]
		)
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "stringVar" : 3, "" : 15 } )

		instancer["contextVariables"][1]["quantize"].setValue( 10 )
		self.assertRaisesRegex(
			Gaffer.ProcessException, 'Instancer.out.attributes : Context variable "0" : cannot quantize variable of type StringVectorData',
			instancer['out'].attributes, "points/instances/withAttrs/0/sphere"
		)
		self.assertRaisesRegex(
			Gaffer.ProcessException, 'Instancer.variations : Context variable "0" : cannot quantize variable of type StringVectorData',
			uniqueCounts
		)


		instancer["contextVariables"][1]["name"].setValue( "colorVar" )
		instancer["contextVariables"][1]["quantize"].setValue( 0 )

		testAttributes( frameAttr = [ 1 ] * 100, floatAttr = floatExpected,
			colorAttr = [ imath.Color3f( i * 0.1 + 2, i * 0.1 + 3, i * 0.1 + 4 ) for i in range(0, 100) ]
		)
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "colorVar" : 100, "" : 100 } )

		instancer["contextVariables"][1]["quantize"].setValue( 1 )
		testAttributes( frameAttr = [ 1 ] * 100, floatAttr = floatExpected,
			colorAttr = [ imath.Color3f( compatRound( i * 0.1 + 2 ), compatRound( i * 0.1 + 3 ), compatRound( i * 0.1 + 4 ) ) for i in range(0, 100) ]
		)
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "colorVar" : 11, "" : 48 } )

		instancer["contextVariables"][1]["name"].setValue( "color4fVar" )
		instancer["contextVariables"][1]["quantize"].setValue( 0 )

		testAttributes( frameAttr = [ 1 ] * 100, floatAttr = floatExpected,
			color4fAttr = [ imath.Color4f( i * 0.1 + 2, i * 0.1 + 3, i * 0.1 + 4, i * 0.1 + 5 ) for i in range(0, 100) ]
		)
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "color4fVar" : 100, "" : 100 } )

		instancer["contextVariables"][1]["quantize"].setValue( 1 )
		testAttributes( frameAttr = [ 1 ] * 100, floatAttr = floatExpected,
			color4fAttr = [ imath.Color4f( compatRound( i * 0.1 + 2 ), compatRound( i * 0.1 + 3 ), compatRound( i * 0.1 + 4 ), compatRound( i * 0.1 + 5 ) ) for i in range(0, 100) ]
		)
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "color4fVar" : 11, "" : 48 } )

		# Set a high quantize so we can see how these variations interact with other types of variations
		instancer["contextVariables"][1]["quantize"].setValue( 10 )
		color4fExpected = [ imath.Color4f( quant( i * 0.1 + 2, 10 ), quant( i * 0.1 + 3, 10 ), quant( i * 0.1 + 4, 10 ), quant( i * 0.1 + 5, 10 ) ) for i in range(0, 100) ]
		testAttributes( frameAttr = [ 1 ] * 100, floatAttr = floatExpected, color4fAttr = color4fExpected )
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "color4fVar" : 4, "" : 20 } )

		instancer["seedEnabled"].setValue( True )
		instancer["rawSeed"].setValue( True )
		testAttributes( frameAttr = [ 1 ] * 100, floatAttr = floatExpected, color4fAttr = color4fExpected, seedAttr = list( range( 100 ) ) )
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "color4fVar" : 4, "seed" : 100, "" : 100 } )

		instancer["rawSeed"].setValue( False )
		instancer["seeds"].setValue( 10 )
		testAttributes( frameAttr = [ 1 ] * 100, floatAttr = floatExpected, color4fAttr = color4fExpected, seedAttr_seedCount = 10 )
		initialFirstVal = instancer['out'].attributes( '/points/instances/withAttrs/0/sphere' )["seedAttr"]
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "color4fVar" : 4, "seed" : 10, "" : 67 } )

		# Changing the seed changes individual values, but not the overall behaviour
		instancer["seedPermutation"].setValue( 1 )
		testAttributes( frameAttr = [ 1 ] * 100, floatAttr = floatExpected, color4fAttr = color4fExpected, seedAttr_seedCount = 10 )
		self.assertNotEqual( initialFirstVal, instancer['out'].attributes( '/points/instances/withAttrs/0/sphere' )["seedAttr"] )
		# Total variation count is a bit different because the different variation sources line up differently
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "color4fVar" : 4, "seed" : 10, "" : 69 } )

		# If we generate 100 seeds from 100 ids, we will get many collisions, and only 67 unique values
		instancer["seeds"].setValue( 100 )
		testAttributes( frameAttr = [ 1 ] * 100, floatAttr = floatExpected, color4fAttr = color4fExpected, seedAttr_seedCount = 67 )
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "color4fVar" : 4, "seed" : 67, "" : 94 } )

		# Now turn on time offset as well and play with everything together
		instancer["seeds"].setValue( 10 )
		instancer["timeOffset"]["enabled"].setValue( True )
		instancer["timeOffset"]["name"].setValue( 'floatVar' )
		instancer["timeOffset"]["quantize"].setValue( 0.0 )
		testAttributes( frameAttr = [ 1 + 2 * math.sin( i ) for i in range(0, 100) ], floatAttr = floatExpected, color4fAttr = color4fExpected, seedAttr_seedCount = 10 )
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "color4fVar" : 4, "seed" : 10, "frame" : 100, "" : 100 } )

		instancer["timeOffset"]["quantize"].setValue( 0.5 )
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "color4fVar" : 4, "seed" : 10, "frame" : 9, "" : 82 } )

		instancer["timeOffset"]["quantize"].setValue( 1 )
		testAttributes( frameAttr = [ i + 1 for i in floatExpected ], floatAttr = floatExpected, color4fAttr = color4fExpected, seedAttr_seedCount = 10 )
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "color4fVar" : 4, "seed" : 10, "frame" : 5, "" : 69 } )
		c = Gaffer.Context()
		c["frame"] = IECore.FloatData( 42 )
		with c:
			testAttributes( frameAttr = [ i + 42 for i in floatExpected ], floatAttr = floatExpected, color4fAttr = color4fExpected, seedAttr_seedCount = 10 )
			self.assertEqual( uniqueCounts(), { "floatVar" : 5, "color4fVar" : 4, "seed" : 10, "frame" : 5, "" : 69 } )

		# Now reduce back down the variations to test different cumulative combinations
		instancer["seedEnabled"].setValue( False )
		testAttributes( frameAttr = [ i + 1 for i in floatExpected ], floatAttr = floatExpected, color4fAttr = color4fExpected )
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "color4fVar" : 4, "frame" : 5, "" : 20 } )

		# With just one context var, driven by the same prim var as frame, with the same quantization,
		# the variations don't multiply
		del instancer["contextVariables"][1]
		testAttributes( frameAttr = [ i + 1 for i in floatExpected ], floatAttr = floatExpected )
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "frame" : 5, "" : 5 } )

		# Using a different source primVar means the variations will multiply
		instancer["timeOffset"]["name"].setValue( 'intVar' )
		instancer["timeOffset"]["quantize"].setValue( 0 )
		testAttributes( frameAttr = [ i + 1 for i in range(100) ], floatAttr = floatExpected )
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "frame" : 100, "" : 100 } )

		instancer["timeOffset"]["quantize"].setValue( 20 )
		testAttributes( frameAttr = [ ((i+10)//20)*20 + 1 for i in range(100) ], floatAttr = floatExpected )
		self.assertEqual( uniqueCounts(), { "floatVar" : 5, "frame" : 6, "" : 30 } )


		# Test with multiple point sources
		pointsMerge = GafferScene.Parent()
		pointsMerge["parent"].setValue( '/' )

		pointSources = []

		for j in range( 3 ):
			points = IECoreScene.PointsPrimitive(
						IECore.V3fVectorData(
							[ imath.V3f( i, 0, 0 ) for i in range( 10 ) ]
						)
					)

			points["floatVar"] = IECoreScene.PrimitiveVariable( IECoreScene.PrimitiveVariable.Interpolation.Vertex, IECore.FloatVectorData(
							[ i * 0.1 + j for i in range( 10 ) ]
						) )
			pointSources.append( GafferScene.ObjectToScene() )
			pointSources[-1]["name"].setValue( "points" )
			pointSources[-1]["object"].setValue( points )
			parent["children"][-1].setInput( pointSources[-1]["out"] )

		instancer["in"].setInput( parent["out"] )
		instancer["timeOffset"]["enabled"].setValue( False )
		instancer["contextVariables"][0]["quantize"].setValue( 0 )
		pointsFilter["paths"].setValue( IECore.StringVectorData( [ '/points*' ] ) )
		self.assertAlmostEqual( instancer['out'].attributes( "points/instances/withAttrs/2/sphere" )["floatAttr"].value, 0.2 )
		self.assertAlmostEqual( instancer['out'].attributes( "points1/instances/withAttrs/3/sphere" )["floatAttr"].value, 1.3 )
		self.assertAlmostEqual( instancer['out'].attributes( "points2/instances/withAttrs/5/sphere" )["floatAttr"].value, 2.5 )
		self.assertEqual( uniqueCounts(), { "floatVar" : 30, "" : 30 } )

		instancer["contextVariables"][0]["quantize"].setValue( 0.2001 )
		self.assertAlmostEqual( instancer['out'].attributes( "points/instances/withAttrs/2/sphere" )["floatAttr"].value, 0.2001, places = 6 )
		self.assertAlmostEqual( instancer['out'].attributes( "points1/instances/withAttrs/3/sphere" )["floatAttr"].value, 1.2006, places = 6 )
		self.assertAlmostEqual( instancer['out'].attributes( "points2/instances/withAttrs/5/sphere" )["floatAttr"].value, 2.4012, places = 6 )
		self.assertEqual( uniqueCounts(), { "floatVar" : 15, "" : 15 } )


		# Test invalid location
		for func in [ instancer["out"].object, instancer["out"].childNames, instancer["out"].bound, instancer["out"].transform ]:
			self.assertRaisesRegex(
				Gaffer.ProcessException,
				'Instancer.out.' + func.__name__ + ' : Instance id "777" is invalid, instancer produces only 10 children.  Topology may have changed during shutter.',
				func, "/points/instances/withAttrs/777"
			)

		# Test passthrough when disabled
		instancer["enabled"].setValue( False )
		self.assertScenesEqual( instancer["in"], instancer["out"] )

	def testContextSet( self ):

		baseSphere = GafferScene.Sphere()
		childSphere = GafferScene.Sphere()

		parent = GafferScene.Parent()
		parent["in"].setInput( baseSphere["out"] )
		parent["children"][0].setInput( childSphere["out"] )
		parent["parent"].setValue( '/sphere' )
		parent["expression"] = Gaffer.Expression()

		# Note that we must supply a default for the value of "seed", since the setNames will be evaluated
		# with no context set
		parent["expression"].setExpression( 'parent["enabled"] = context.get( "seed", 0 ) % 2' )

		allFilter = GafferScene.PathFilter()
		allFilter["paths"].setValue( IECore.StringVectorData( [ '/...' ] ) )

		setNode = GafferScene.Set()
		setNode["in"].setInput( parent["out"] )
		setNode["filter"].setInput( allFilter["out"] )

		plane = GafferScene.Plane()

		pathFilter = GafferScene.PathFilter()
		pathFilter["paths"].setValue( IECore.StringVectorData( [ '/plane' ] ) )

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( plane["out"] )
		instancer["filter"].setInput( pathFilter["out"] )
		instancer["prototypes"].setInput( setNode["out"] )
		instancer["rawSeed"].setValue( True )


		with Gaffer.Context() as c :
			c["seed"] = 0
			self.assertEqual(
				set( instancer["out"].set( "set" ).value.paths() ),
				set( [ "/plane/instances/sphere/" + i for i in [ "0", "1", "2", "3" ] ] )
			)
			c["seed"] = 1
			self.assertEqual(
				set( instancer["out"].set( "set" ).value.paths() ),
				set( [ "/plane/instances/sphere/" + i for i in
					[ "0", "1", "2", "3", "0/sphere", "1/sphere", "2/sphere", "3/sphere" ] ]
				)
			)

		instancer["seedEnabled"].setValue( True )
		self.assertEqual(
			set( instancer["out"].set( "set" ).value.paths() ),
			set( [ "/plane/instances/sphere/" + i for i in [ "0", "1", "2", "3", "1/sphere", "3/sphere" ] ] )
		)

		# When encapsulating, we shouldn't pay any time cost for evaluating the set, even with a huge
		# number of instances
		plane["divisions"].setValue( imath.V2i( 1000 ) )
		instancer["encapsulateInstanceGroups"].setValue( True )
		t = time.time()
		instancer["out"].set( "set" )
		totalTime = time.time() - t
		self.assertLess( totalTime, 0.001 )

		# Test passthrough when disabled
		instancer["enabled"].setValue( False )
		self.assertScenesEqual( instancer["in"], instancer["out"] )

	def testRootPerVertexWithEmptyPoints( self ) :

		points = IECoreScene.PointsPrimitive( IECore.V3fVectorData() )
		self.assertEqual( points.numPoints, 0 )

		points["prototypeRoots"] = IECoreScene.PrimitiveVariable(
			IECoreScene.PrimitiveVariable.Interpolation.Vertex,
			# OK to have no values to index, because we have no vertices that
			# need to index them. One common way to end up with data like this
			# is to use DeletePoints, which will remove any values that aren't
			# indexed after deletion.
			IECore.StringVectorData(),
			# Empty index list, because the primitive has no vertices.
			IECore.IntVectorData(),
		)
		self.assertTrue( points.arePrimitiveVariablesValid() )

		pointsScene = GafferScene.ObjectToScene()
		pointsScene["object"].setValue( points )
		pointsScene["name"].setValue( "points" )

		sphere = GafferScene.Sphere()
		cube = GafferScene.Cube()

		prototypes = GafferScene.Group()
		prototypes["in"][0].setInput( sphere["out"] )
		prototypes["in"][1].setInput( cube["out"] )

		pointsFilter = GafferScene.PathFilter()
		pointsFilter["paths"].setValue( IECore.StringVectorData( [ "/points" ] ) )

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( pointsScene["out"] )
		instancer["prototypes"].setInput( prototypes["out"] )
		instancer["filter"].setInput( pointsFilter["out"] )
		instancer["prototypeMode"].setValue( instancer.PrototypeMode.RootPerVertex )

		self.assertEqual( instancer["out"].childNames( "/points" ), IECore.InternedStringVectorData( [ "instances" ] ) )
		self.assertEqual( instancer["out"].childNames( "/points/instances" ), IECore.InternedStringVectorData() )
		self.assertSceneValid( instancer["out"] )

	def runTestContextSetPerf( self, useContexts, parallelEvaluate ):

		plane = GafferScene.Plane()
		plane["divisions"].setValue( imath.V2i( 1000 ) )
		plane["divisionExpression"] = Gaffer.Expression()
		plane["divisionExpression"].setExpression( 'parent["divisions"] = imath.V2i( 1000 + int( context["collect:rootName"][-1:] ) )' )

		# Duplicate the source points, so that we are measuring the perf of an Instancer targeting multiple locations
		collectScenes = GafferScene.CollectScenes()
		collectScenes["in"].setInput( plane["out"] )
		collectScenes["rootNames"].setValue( IECore.StringVectorData( [ 'plane0', 'plane1', 'plane2', 'plane3', 'plane4' ] ) )
		collectScenes["sourceRoot"].setValue( '/plane' )

		# Source scene, with a little hierarchy, so paths aren't trivial to merge
		sphere = GafferScene.Sphere()

		group = GafferScene.Group( "group" )
		group["in"][0].setInput( sphere["out"] )


		# Create a set
		leafFilter = GafferScene.PathFilter()
		leafFilter["paths"].setValue( IECore.StringVectorData( [ '/group/sphere' ] ) )

		setNode = GafferScene.Set()
		setNode["in"].setInput( group["out"] )
		setNode["filter"].setInput( leafFilter["out"] )

		# Instancer
		instancerFilter = GafferScene.PathFilter()
		instancerFilter["paths"].setValue( IECore.StringVectorData( [ '/plane*' ] ) )

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( collectScenes["out"] )
		instancer["filter"].setInput( instancerFilter["out"] )
		instancer["prototypes"].setInput( setNode["out"] )
		instancer["seedEnabled"].setValue( useContexts )

		if not parallelEvaluate:
			with GafferTest.TestRunner.PerformanceScope() :
				instancer["out"].set( "set" )
		else:
			# Set up a slightly realistic scene which results in the set plug being
			# pulled multiple times in parallel, to check whether TaskCollaborate is working
			setFilter = GafferScene.SetFilter()
			setFilter["setExpression"].setValue( 'set' )

			customAttributes = GafferScene.CustomAttributes()
			customAttributes["attributes"].addChild( Gaffer.NameValuePlug( "", Gaffer.BoolPlug( "value", defaultValue = False, flags = Gaffer.Plug.Flags.Default | Gaffer.Plug.Flags.Dynamic, ), True, "member1", Gaffer.Plug.Flags.Default | Gaffer.Plug.Flags.Dynamic ) )
			customAttributes["in"].setInput( instancer["out"] )
			customAttributes["filter"].setInput( setFilter["out"] )
			customAttributes["attributes"]["member1"]["name"].setValue( 'testAttr' )
			customAttributes["attributes"]["member1"]["value"].setValue( True )

			subTree = GafferScene.SubTree()
			subTree["in"].setInput( customAttributes["out"] )
			subTree["root"].setValue( '/plane0/instances/group' )

			isolateFilter = GafferScene.PathFilter()
			isolateFilter["paths"].setValue( IECore.StringVectorData( [ '/67000*' ] ) )

			isolate = GafferScene.Isolate()
			isolate["in"].setInput( subTree["out"] )
			isolate["filter"].setInput( isolateFilter["out"] )

			with GafferTest.TestRunner.PerformanceScope() :
				GafferSceneTest.traverseScene( isolate["out"] )

	def testEmptyPrototypes( self ) :

		plane = GafferScene.Plane()

		planeFilter = GafferScene.PathFilter()
		planeFilter["paths"].setValue( IECore.StringVectorData( [ "/plane" ] ) )

		instancer = GafferScene.Instancer()
		instancer["in"].setInput( plane["out"] )
		instancer["filter"].setInput( planeFilter["out"] )

		self.assertEqual( instancer["variations"].getValue(), IECore.CompoundData( { "" : IECore.IntData( 0 ) } ) )

	@unittest.skipIf( GafferTest.inCI(), "Performance not relevant on CI platform" )
	@GafferTest.TestRunner.PerformanceTestMethod()
	def testContextSetPerfNoVariationsSingleEvaluate( self ):
		self.runTestContextSetPerf( False, False )

	@unittest.skipIf( GafferTest.inCI(), "Performance not relevant on CI platform" )
	@GafferTest.TestRunner.PerformanceTestMethod()
	def testContextSetPerfNoVariationsParallelEvaluate( self ):
		self.runTestContextSetPerf( False, True )

	@unittest.skipIf( GafferTest.inCI(), "Performance not relevant on CI platform" )
	@GafferTest.TestRunner.PerformanceTestMethod()
	def testContextSetPerfWithVariationsSingleEvaluate( self ):
		self.runTestContextSetPerf( True, False )

	@unittest.skipIf( GafferTest.inCI(), "Performance not relevant on CI platform" )
	@GafferTest.TestRunner.PerformanceTestMethod()
	def testContextSetPerfWithVariationsParallelEvaluate( self ):
		self.runTestContextSetPerf( True, True )


if __name__ == "__main__":
	unittest.main()
